"""
FastAPI application for JSON Link Viewer & Editor
Supports multi-user concurrent editing with conflict detection
Features: In-memory data management, batch saving, real-time statistics
"""
from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
from filelock import FileLock
import hashlib
from collections import defaultdict, Counter
import tempfile

# Configure logging with immediate flushing for Cloud Run
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)
logger = logging.getLogger(__name__)

# Force unbuffered output for Cloud Run
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

app = FastAPI(title="JSON Link Viewer & Editor")

# Configuration
DATA_FOLDER = Path(os.getenv("DATA_FOLDER", "."))
DATA_FILE = DATA_FOLDER / "tmp_lh_links.json"
LOCK_FILE = DATA_FOLDER / "tmp_lh_links.json.lock"
ADMIN_USER = os.getenv("ADMIN_USER", "danny")
PORT = int(os.getenv("PORT", "7860"))

# Batch save configuration
SAVE_THRESHOLD_MODIFICATIONS = int(os.getenv("SAVE_THRESHOLD_MODIFICATIONS", "3"))

# Global data manager instance
data_manager = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DataManager:
    """
    Centralized in-memory data manager with batch saving and statistics
    """
    def __init__(self):
        self.in_memory_data: List[Dict[str, Any]] = []
        self.modification_count: int = 0
        self.last_save_time: Optional[datetime] = None
        self.last_save_error: Optional[str] = None
        self.data_version: str = ""
        self.user_activity: Dict[str, datetime] = {}  # Track active users
        self.user_current_record: Dict[str, int] = {}  # Track which record each user is viewing
        self.upload_timestamp: Optional[datetime] = None  # Track when upload happened
        self.lock = asyncio.Lock()
        
    async def initialize(self):
        """Load initial data from disk"""
        async with self.lock:
            self.in_memory_data = await self._load_from_disk()
            self.data_version = self._compute_hash(self.in_memory_data)
            
            # Set last_save_time to the file's actual modification time
            if DATA_FILE.exists():
                file_mtime = datetime.fromtimestamp(DATA_FILE.stat().st_mtime)
                self.last_save_time = file_mtime
                logger.info(f"📅 Last file save was at: {file_mtime.isoformat()}")
            else:
                self.last_save_time = datetime.now()
            
            self.modification_count = 0
            self.last_save_error = None
            logger.info(f"✅ DataManager initialized with {len(self.in_memory_data)} records")
    
    def _compute_hash(self, data: List[Dict]) -> str:
        """Compute hash of data for version tracking"""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    async def _load_from_disk(self) -> List[Dict[str, Any]]:
        """Load data from JSON file with file locking"""
        if not DATA_FILE.exists():
            return []
        
        file_lock = FileLock(str(LOCK_FILE))
        with file_lock:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    async def _save_to_disk(self) -> bool:
        """Save data to JSON file with file locking and atomic writes. Returns success status.
        
        IMPORTANT: This method assumes the caller already holds self.lock to ensure
        thread-safety. All public methods that call this must acquire self.lock first.
        """
        temp_file = None
        try:
            logger.info("="*60)
            logger.info(f"💾 ATTEMPTING SAVE TO DISK: {len(self.in_memory_data)} records")
            logger.info(f"   File: {DATA_FILE.absolute()}")
            logger.info(f"   File exists: {DATA_FILE.exists()}")
            logger.info(f"   Parent directory: {DATA_FILE.parent.absolute()}")
            logger.info(f"   Parent writable: {os.access(DATA_FILE.parent, os.W_OK)}")
            logger.info(f"   Modifications being saved: {self.modification_count}")
            
            # Use lock file based on DATA_FILE, not global LOCK_FILE
            lock_file = str(DATA_FILE) + '.lock'
            file_lock = FileLock(lock_file)
            logger.info(f"   Lock file: {lock_file}")
            
            with file_lock:
                logger.info(f"   🔒 Lock acquired")
                
                # Write to temporary file first (atomic write pattern)
                logger.info(f"   ✍️  Writing JSON data to temp file...")
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    dir=DATA_FILE.parent,
                    delete=False,
                    suffix='.tmp'
                ) as f:
                    temp_file = f.name
                    json.dump(self.in_memory_data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                
                logger.info(f"   ✍️  Temp file written, performing atomic rename...")
                
                # Atomic rename (replaces existing file)
                os.rename(temp_file, DATA_FILE)
                temp_file = None  # Successfully moved
                
                logger.info(f"   ✍️  File renamed, checking...")
                
                if not DATA_FILE.exists():
                    raise Exception(f"File does not exist after rename: {DATA_FILE}")
                
                file_size = DATA_FILE.stat().st_size
                file_mtime = datetime.fromtimestamp(DATA_FILE.stat().st_mtime)
                
                logger.info(f"✅ DISK WRITE COMPLETE!")
                logger.info(f"   File size: {file_size:,} bytes")
                logger.info(f"   File mtime: {file_mtime.isoformat()}")
                logger.info(f"   Saved at: {datetime.now().isoformat()}")
                logger.info("="*60)
                
                # Only reset counters after successful atomic write
                self.last_save_time = datetime.now()
                self.modification_count = 0
                self.last_save_error = None
                return True
        except Exception as e:
            error_msg = f"Save failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            self.last_save_error = error_msg
            # Clean up temp file if it still exists
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.info(f"   🧹 Cleaned up temp file: {temp_file}")
                except Exception as cleanup_error:
                    logger.error(f"   ❌ Failed to clean up temp file: {cleanup_error}")
            return False
    
    async def get_data(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Get current in-memory data with metadata"""
        async with self.lock:
            if username:
                self.user_activity[username] = datetime.now()
            
            # Check if client needs to reload due to upload
            reload_required = False
            if self.upload_timestamp:
                # If upload happened in last 5 seconds, tell clients to reload
                if datetime.now() - self.upload_timestamp < timedelta(seconds=5):
                    reload_required = True
            
            return {
                "data": self.in_memory_data,
                "version": self.data_version,
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "unsaved_changes": self.modification_count,
                "last_save": self.last_save_time.isoformat() if self.last_save_time else None,
                "save_error": self.last_save_error,
                "reload_required": reload_required
            }
    
    async def update_record(self, index: int, updates: Dict[str, Any], username: Optional[str] = None) -> Dict[str, Any]:
        """Update a single record in memory"""
        async with self.lock:
            if index < 0 or index >= len(self.in_memory_data):
                raise ValueError(f"Invalid index: {index}")
            
            # Apply updates
            old_status = self.in_memory_data[index].get("Status")
            for key, value in updates.items():
                self.in_memory_data[index][key] = value
            
            # Track who made the change if Status changed
            new_status = self.in_memory_data[index].get("Status")
            if username and old_status != new_status:
                self.in_memory_data[index]["fixed_by"] = username
                self.in_memory_data[index]["fixed_at"] = datetime.now().isoformat()
            
            # Update tracking
            self.modification_count += 1
            logger.info(f"📝 Record updated at index {index}. Modification count: {self.modification_count}")
            self.data_version = self._compute_hash(self.in_memory_data)
            
            if username:
                self.user_activity[username] = datetime.now()
            
            # Check if auto-save should trigger (already have lock, so check directly)
            save_triggered = False
            if self.modification_count >= SAVE_THRESHOLD_MODIFICATIONS:
                logger.info(f"🔄 Save triggered: {self.modification_count} modifications >= {SAVE_THRESHOLD_MODIFICATIONS}")
                save_triggered = await self._save_to_disk()
            
            return {
                "status": "success",
                "modification_count": self.modification_count,
                "version": self.data_version,
                "auto_saved": save_triggered
            }
    
    async def replace_all_data(self, new_data: List[Dict[str, Any]], username: Optional[str] = None, expected_version: Optional[str] = None) -> Dict[str, Any]:
        """Replace all data (used by upload and legacy save)
        
        Args:
            new_data: New data to replace existing data
            username: User making the change
            expected_version: Expected version for conflict detection (optional)
        
        Returns:
            Dict with status, message, and version info
        """
        async with self.lock:
            # Check for conflicts if expected version provided
            if expected_version and expected_version != self.data_version:
                return {
                    "status": "conflict",
                    "message": "Data has been modified by another user. Please reload.",
                    "current_version": self.data_version,
                    "expected_version": expected_version
                }
            
            self.in_memory_data = new_data
            self.data_version = self._compute_hash(self.in_memory_data)
            self.upload_timestamp = datetime.now()
            
            # Save immediately - only reset modification_count after successful save
            success = await self._save_to_disk()
            
            # modification_count is reset in _save_to_disk() if successful
            # If save failed, keep the count so auto-save will retry
            
            return {
                "status": "success" if success else "error",
                "message": "Data replaced and saved" if success else "Data replaced but save failed",
                "items": len(self.in_memory_data),
                "version": self.data_version,
                "save_error": self.last_save_error
            }
    
    async def check_and_save(self) -> bool:
        """Check if save is needed and perform it. Returns True if saved."""
        async with self.lock:
            # Save when modification count reaches threshold
            if self.modification_count >= SAVE_THRESHOLD_MODIFICATIONS:
                logger.info(f"🔄 Save triggered: {self.modification_count} modifications >= {SAVE_THRESHOLD_MODIFICATIONS}")
                return await self._save_to_disk()
            
            return False
    
    async def force_save(self) -> Dict[str, Any]:
        """Force immediate save (admin function)"""
        async with self.lock:
            mod_count_before_save = self.modification_count
            success = await self._save_to_disk()
            return {
                "status": "success" if success else "error",
                "message": f"Saved {len(self.in_memory_data)} records to {DATA_FILE.absolute()}" if success else "Save failed",
                "error": self.last_save_error,
                "modifications_saved": mod_count_before_save,
                "file_path": str(DATA_FILE.absolute()),
                "file_exists": DATA_FILE.exists(),
                "file_size": DATA_FILE.stat().st_size if DATA_FILE.exists() else 0,
                "last_save_time": self.last_save_time.isoformat() if self.last_save_time else None
            }
    
    def _cleanup_stale_sessions(self):
        """Remove inactive users (>10 minutes)"""
        now = datetime.now()
        stale_users = [
            user for user, last_active in self.user_activity.items()
            if now - last_active > timedelta(minutes=10)
        ]
        for user in stale_users:
            logger.info(f"🧹 Cleaning up stale session for user: {user}")
            del self.user_activity[user]
            if user in self.user_current_record:
                del self.user_current_record[user]
    
    async def get_next_record(
        self,
        username: str,
        current_index: Optional[int] = None,
        filter_status: Optional[str] = None,
        filter_llm_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find next available record that matches filters and is not in use by another user"""
        async with self.lock:
            # Update user activity
            self.user_activity[username] = datetime.now()
            
            # Cleanup stale sessions
            self._cleanup_stale_sessions()
            
            # Get set of indices currently being viewed by other users
            occupied_indices = {
                idx for user, idx in self.user_current_record.items()
                if user != username
            }
            
            # Start searching from current_index + 1, or 0 if not provided
            start_index = (current_index + 1) if current_index is not None else 0
            
            # Search for next matching record
            for offset in range(len(self.in_memory_data)):
                idx = (start_index + offset) % len(self.in_memory_data)
                
                # Skip if occupied
                if idx in occupied_indices:
                    continue
                
                record = self.in_memory_data[idx]
                
                # Apply filters
                if filter_status and record.get("Status") != filter_status:
                    continue
                
                if filter_llm_status and record.get("LLMStatus") != filter_llm_status:
                    continue
                
                # Found a match - mark as in use
                self.user_current_record[username] = idx
                
                logger.info(f"📍 User {username} assigned to record {idx} (skipped {len(occupied_indices)} occupied)")
                
                return {
                    "index": idx,
                    "record": record,
                    "occupied_count": len(occupied_indices),
                    "active_users": list(self.user_activity.keys())
                }
            
            # No matching record found
            return {
                "index": None,
                "record": None,
                "occupied_count": len(occupied_indices),
                "active_users": list(self.user_activity.keys()),
                "message": "No available records matching filters"
            }
    
    async def get_stats(self, filter_status: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about current data (with proper locking)"""
        async with self.lock:
            # Compute stats from in-memory data (includes unsaved changes)
            status_counts = Counter(item.get("Status", "unknown") for item in self.in_memory_data)
            
            # Filter if requested
            visible_records = len(self.in_memory_data)
            if filter_status:
                visible_records = status_counts.get(filter_status, 0)
            
            # Active users (active in last 5 minutes)
            now = datetime.now()
            active_users = [
                user for user, last_active in self.user_activity.items()
                if now - last_active < timedelta(minutes=5)
            ]
            
            return {
                "total_records": len(self.in_memory_data),
                "visible_records": visible_records,
                "by_status": dict(status_counts),
                "unsaved_changes": self.modification_count,
                "last_save": self.last_save_time.isoformat() if self.last_save_time else None,
                "last_save_error": self.last_save_error,
                "active_users": len(active_users),
                "active_user_names": active_users
            }


@app.on_event("startup")
async def startup_event():
    """Initialize data manager"""
    global data_manager
    data_manager = DataManager()
    await data_manager.initialize()
    logger.info(f"🚀 Auto-save enabled (saves every {SAVE_THRESHOLD_MODIFICATIONS} modifications)")


@app.on_event("shutdown")
async def shutdown_event():
    """Save data on shutdown"""
    if data_manager and data_manager.modification_count > 0:
        logger.info("💾 Saving unsaved changes on shutdown...")
        await data_manager.force_save()


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
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    return await data_manager.get_data(username)


@app.get("/version")
async def get_version():
    """Get current data version (for conflict detection)"""
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    return {
        "version": data_manager.data_version,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/stats")
async def get_stats(
    username: Optional[str] = Header(None, alias="X-Username"),
    filter_status: Optional[str] = None
):
    """Get statistics about the data"""
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    stats = await data_manager.get_stats(filter_status)
    return stats


@app.get("/next")
async def get_next_record(
    username: Optional[str] = Header(None, alias="X-Username"),
    current_index: Optional[int] = None,
    filter_status: Optional[str] = None,
    filter_llm_status: Optional[str] = None
):
    """Get the next available record that matches filters and is not being viewed by another user"""
    if not username:
        raise HTTPException(status_code=400, detail="Username header required")
    
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    logger.info(f"🔍 /next called by {username}, current_index={current_index}, filters: status={filter_status}, llm={filter_llm_status}")
    
    result = await data_manager.get_next_record(
        username=username,
        current_index=current_index,
        filter_status=filter_status,
        filter_llm_status=filter_llm_status
    )
    
    return result


@app.post("/update")
async def update_record(
    request: Request,
    username: Optional[str] = Header(None, alias="X-Username")
):
    """Update a single record (fast, in-memory only)"""
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    body = await request.json()
    index = body.get("index")
    updates = body.get("updates", {})
    
    logger.info(f"📨 /update endpoint called: index={index}, updates={updates}, username={username}")
    
    if index is None:
        raise HTTPException(status_code=400, detail="Missing 'index' field")
    
    try:
        logger.info(f"🔄 Calling data_manager.update_record for index {index}")
        result = await data_manager.update_record(index, updates, username)
        logger.info(f"✅ update_record returned: {result}")
        return result
    except ValueError as e:
        logger.error(f"❌ ValueError in update_record: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error in update_record: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.post("/force-save")
async def force_save(username: Optional[str] = Header(None, alias="X-Username")):
    """Force immediate save (admin only)"""
    logger.info(f"🔨 /force-save endpoint called by username={username}")
    logger.info(f"   Admin user configured as: {ADMIN_USER}")
    
    if username != ADMIN_USER:
        logger.warning(f"❌ Force save denied: '{username}' is not admin '{ADMIN_USER}'")
        raise HTTPException(
            status_code=403,
            detail=f"Only user '{ADMIN_USER}' can force save"
        )
    
    if not data_manager:
        logger.error("❌ Data manager not initialized!")
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    logger.info("🔄 Calling data_manager.force_save()")
    result = await data_manager.force_save()
    logger.info(f"✅ Force save completed: {result}")
    return result


@app.post("/save")
async def save_changes(
    request: Request,
    username: Optional[str] = Header(None, alias="X-Username"),
    client_version: Optional[str] = Header(None, alias="X-Data-Version")
):
    """Save changes - LEGACY endpoint, now saves entire dataset to memory and triggers save"""
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    # Parse the incoming data
    body = await request.json()
    new_data = body if isinstance(body, list) else body.get("data", [])
    
    # Replace all data (version check is now atomic inside replace_all_data)
    result = await data_manager.replace_all_data(new_data, username, expected_version=client_version)
    
    # Check for conflicts
    if result.get("status") == "conflict":
        return JSONResponse(
            status_code=409,
            content={
                "error": "conflict",
                "message": result["message"],
                "current_version": result["current_version"]
            }
        )
    
    return {
        "status": result["status"],
        "message": result["message"],
        "version": result["version"],
        "timestamp": datetime.now().isoformat(),
        "saved_by": username,
        "save_error": result.get("save_error")
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
    
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    # Validate JSON
    try:
        content = await file.read()
        new_data = json.loads(content.decode('utf-8'))
        if not isinstance(new_data, list):
            raise ValueError("JSON must be an array")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    
    # Replace all data and save immediately
    result = await data_manager.replace_all_data(new_data, username)
    
    return {
        "status": result["status"],
        "message": f"File uploaded successfully by {username}. Other users will be notified to reload.",
        "items": len(new_data),
        "version": result["version"],
        "saved_to": str(DATA_FILE.absolute()),
        "save_error": result.get("save_error")
    }


@app.get("/download")
async def download_file(username: Optional[str] = Header(None, alias="X-Username")):
    """Download the current JSON file (admin only) - includes unsaved changes from memory"""
    if username != ADMIN_USER:
        raise HTTPException(
            status_code=403,
            detail=f"Only user '{ADMIN_USER}' can download files"
        )
    
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    # Get current in-memory data (includes unsaved changes)
    data_info = await data_manager.get_data(username)
    current_data = data_info["data"]
    
    # Create temporary file with current data
    temp_file = DATA_FOLDER / f"tmp_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
    
    try:
        response = FileResponse(
            path=temp_file,
            filename=f"tmp_lh_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            media_type="application/json"
        )
        response.headers["X-File-Path"] = str(DATA_FILE.absolute())
        response.headers["X-Unsaved-Changes"] = str(data_info["unsaved_changes"])
        return response
    finally:
        # Clean up temp file after response (done in background)
        pass


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
        # Load LM JSON from app's data/ folder (constants, not user data)
        lm_file = Path("data") / "Likutei_Moharan_refs.json"
        if not lm_file.exists():
            raise HTTPException(status_code=404, detail=f"Likutei Moharan JSON not found at {lm_file.absolute()}")
        
        with open(lm_file, 'r', encoding='utf-8') as f:
            lm_data = json.load(f)
        
        # Parse the reference path (e.g., "Likutei Moharan.61.1.3" or "Likutei Moharan%2C_Part_II.23.1.5")
        # Decode URL encoding
        ref_path = ref_path.replace('%2C_', ', ')
        # Replace underscores with spaces in the book name (first part before the first dot)
        # Sefaria uses underscores in URLs but the JSON uses spaces
        parts = ref_path.split('.')
        if parts:
            parts[0] = parts[0].replace('_', ' ')
        
        logger.info(f"📖 Looking up reference: original={ref_path}, parts={parts}")
        logger.info(f"   Available top-level keys: {list(lm_data.keys())}")
        
        # Navigate through the JSON structure
        current = lm_data
        for i, part in enumerate(parts):
            logger.info(f"   Step {i}: navigating with part='{part}', current type={type(current).__name__}")
            if isinstance(current, dict):
                logger.info(f"      Dict keys available: {list(current.keys())[:10]}")
                current = current.get(part)
                logger.info(f"      After get('{part}'): {type(current).__name__ if current else 'None'}")
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
                logger.error(f"❌ Reference not found at step {i}, part='{part}'")
                raise HTTPException(status_code=404, detail=f"Reference not found: {'.'.join(parts)} (failed at part '{part}')")
        
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
    logger.info(f"Starting server on port {PORT}")
    logger.info(f"Admin user: {ADMIN_USER}")
    logger.info(f"Data folder: {DATA_FOLDER.absolute()}")
    logger.info(f"Data folder writable: {os.access(DATA_FOLDER, os.W_OK)}")
    logger.info(f"Data file path: {DATA_FILE.absolute()}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
