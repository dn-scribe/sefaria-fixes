"""
FastAPI application for JSON Link Viewer & Editor
Supports multi-user concurrent editing with conflict detection
"""
from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncio
from filelock import FileLock
import hashlib

app = FastAPI(title="JSON Link Viewer & Editor")

# Configuration
DATA_FOLDER = Path(os.getenv("DATA_FOLDER", "."))
DATA_FILE = DATA_FOLDER / "tmp_lh_links.json"
LOCK_FILE = DATA_FOLDER / "tmp_lh_links.json.lock"
ADMIN_USER = os.getenv("ADMIN_USER", "danny")
PORT = int(os.getenv("PORT", "7860"))

# In-memory cache for version tracking
data_version = {"hash": None, "timestamp": None}
lock = asyncio.Lock()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compute_hash(data: List[Dict]) -> str:
    """Compute hash of data for version tracking"""
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def load_data() -> List[Dict[str, Any]]:
    """Load data from JSON file with file locking"""
    if not DATA_FILE.exists():
        return []
    
    file_lock = FileLock(str(LOCK_FILE))
    with file_lock:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Update version tracking
            data_version["hash"] = compute_hash(data)
            data_version["timestamp"] = datetime.now().isoformat()
            return data


def save_data(data: List[Dict[str, Any]]) -> None:
    """Save data to JSON file with file locking"""
    file_lock = FileLock(str(LOCK_FILE))
    with file_lock:
        print(f"Saving data to: {DATA_FILE.absolute()}")
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Data saved successfully. File size: {DATA_FILE.stat().st_size} bytes")
        # Update version tracking
        data_version["hash"] = compute_hash(data)
        data_version["timestamp"] = datetime.now().isoformat()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the HTML viewer"""
    html_file = Path("json-viewer.html")
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="HTML file not found")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        return f.read()


@app.get("/data")
async def get_data(username: Optional[str] = Header(None, alias="X-Username")):
    """Get the current JSON data with version info"""
    async with lock:
        data = load_data()
        return {
            "data": data,
            "version": data_version["hash"],
            "timestamp": data_version["timestamp"],
            "username": username
        }


@app.get("/version")
async def get_version():
    """Get current data version (for conflict detection)"""
    return {
        "version": data_version["hash"],
        "timestamp": data_version["timestamp"]
    }


@app.post("/save")
async def save_changes(
    request: Request,
    username: Optional[str] = Header(None, alias="X-Username"),
    client_version: Optional[str] = Header(None, alias="X-Data-Version")
):
    """Save changes with conflict detection and fixed_by tracking"""
    async with lock:
        # Get current data to check for conflicts
        current_data = load_data()
        current_hash = data_version["hash"]
        
        # Check for conflicts if client provided version
        if client_version and client_version != current_hash:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "conflict",
                    "message": "Data has been modified by another user. Please reload.",
                    "current_version": current_hash
                }
            )
        
        # Parse the incoming data
        body = await request.json()
        new_data = body if isinstance(body, list) else body.get("data", [])
        
        # Track changes and update fixed_by field
        if username and current_data:
            for i, new_item in enumerate(new_data):
                if i < len(current_data):
                    old_item = current_data[i]
                    # Check if Status changed
                    if new_item.get("Status") != old_item.get("Status"):
                        new_item["fixed_by"] = username
                        new_item["fixed_at"] = datetime.now().isoformat()
        
        # Save the new data
        save_data(new_data)
        
        return {
            "status": "success",
            "message": "Data saved successfully",
            "version": data_version["hash"],
            "timestamp": data_version["timestamp"],
            "saved_by": username
        }


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    username: Optional[str] = Header(None, alias="X-Username")
):
    """Upload a new JSON file (admin only)"""
    if username != ADMIN_USER:
        raise HTTPException(
            status_code=403, 
            detail=f"Only user '{ADMIN_USER}' can upload files"
        )
    
    # Validate JSON
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        if not isinstance(data, list):
            raise ValueError("JSON must be an array")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    
    # Save the data
    async with lock:
        save_data(data)
    
    return {
        "status": "success",
        "message": f"File uploaded successfully by {username}",
        "items": len(data),
        "version": data_version["hash"],
        "saved_to": str(DATA_FILE.absolute())
    }


@app.get("/download")
async def download_file(username: Optional[str] = Header(None, alias="X-Username")):
    """Download the current JSON file (admin only)"""
    if username != ADMIN_USER:
        raise HTTPException(
            status_code=403, 
            detail=f"Only user '{ADMIN_USER}' can download files"
        )
    
    if not DATA_FILE.exists():
        raise HTTPException(status_code=404, detail="Data file not found")
    
    response = FileResponse(
        path=DATA_FILE,
        filename=f"tmp_lh_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        media_type="application/json"
    )
    response.headers["X-File-Path"] = str(DATA_FILE.absolute())
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Try to get git commit hash
    commit_hash = os.getenv("GIT_COMMIT", "unknown")
    if commit_hash == "unknown":
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                commit_hash = result.stdout.strip()
        except Exception:
            pass
    
    return {
        "status": "healthy",
        "data_file_exists": DATA_FILE.exists(),
        "admin_user": ADMIN_USER,
        "timestamp": datetime.now().isoformat(),
        "commit": commit_hash,
        "data_folder": str(DATA_FOLDER.absolute())
    }


@app.get("/lm-paragraph/{ref_path:path}")
async def get_lm_paragraph(ref_path: str):
    """Get Likutei Moharan paragraph text from reference path"""
    try:
        # Load LM JSON
        lm_file = DATA_FOLDER / "Likutei_Moharan_refs.json"
        if not lm_file.exists():
            raise HTTPException(status_code=404, detail="Likutei Moharan JSON not found")
        
        with open(lm_file, 'r', encoding='utf-8') as f:
            lm_data = json.load(f)
        
        # Parse the reference path (e.g., "Likutei Moharan.61.1.3" or "Likutei Moharan%2C_Part_II.23.1.5")
        # Decode URL encoding
        ref_path = ref_path.replace('%2C_', ', ')
        parts = ref_path.split('.')
        
        # Navigate through the JSON structure
        current = lm_data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part) - 1  # Convert to 0-based index
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        current = None
                except (ValueError, IndexError):
                    current = None
            else:
                current = None
            
            if current is None:
                raise HTTPException(status_code=404, detail=f"Reference not found: {ref_path}")
        
        # Return the text
        if isinstance(current, str):
            return {"text": current, "ref": ref_path}
        else:
            raise HTTPException(status_code=400, detail="Reference does not point to a text paragraph")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching paragraph: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Ensure data folder exists
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    print(f"Starting server on port {PORT}")
    print(f"Admin user: {ADMIN_USER}")
    print(f"Data folder: {DATA_FOLDER.absolute()}")
    print(f"Data folder writable: {os.access(DATA_FOLDER, os.W_OK)}")
    print(f"Data file path: {DATA_FILE.absolute()}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
