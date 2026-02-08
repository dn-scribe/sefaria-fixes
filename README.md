---
title: Linking LH
emoji: 🔗
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
license: mit
app_port: 7860
---
# Linking LH (Sefaria Fixes)

A collaborative web app for reviewing and editing JSON link data between Likutei Halakhot and Likutei Moharan.  
The client never loads the full dataset; it works on a single record at a time. The server owns all data, assignment, and saves.

**Live App:** https://dn-9281411-linking-lh.hf.space/

## Architecture

- **Server:** `app.py` (FastAPI)
  - Loads the full JSON dataset into memory.
  - Assigns **one record at a time** to each active session (`/next`).
  - Prevents concurrent users (or tabs) from editing the same record.
  - Batches updates and auto-saves after N modifications.
- **Client:** `jsov-viewer.html`
  - Prompts for username on load.
  - Uses a **per-tab session ID** (`X-Session-Id`) to avoid multi-tab collisions.
  - Only holds the current record and stats, never the full dataset.

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open:
```
http://localhost:7860
```

## Environment Variables

- `ADMIN_USER` (default: `danny`)  
  Username allowed to upload/download/force-save.
- `PORT` (default: `7860`)
- `DATA_FOLDER` (default: `.`)
- `SAVE_THRESHOLD_MODIFICATIONS` (default: `3`)

## UX Flow

1. User opens the page and enters a username.
2. The server assigns a **single record** for review.
3. Users can edit fields and save; updates are sent as diffs.
4. Navigation uses `/next` (server selects the next unoccupied record).
5. Admin (`ADMIN_USER`) can upload, download, and force-save.

## API Endpoints

### Public
- `GET /` - Web interface (`jsov-viewer.html`)
- `GET /health` - Health check / version info
- `GET /stats` - Aggregated stats (cached server-side)
- `GET /next` - Next available record
- `GET /record?index=N` - Fetch specific record (if not occupied)
- `POST /update` - Update a single record (diff-based)

### Admin Only
- `POST /upload` - Upload a new JSON file
- `GET /download` - Download current data (includes in-memory unsaved changes)
- `POST /force-save` - Force write to disk

### Required Headers

All client requests include:
```bash
X-Username: <username>
X-Session-Id: <unique-per-tab-id>
```

## Data Fields

Each item is expected to include:

- `RefA`, `RefALink`
- `RefB`, `RefBLink`, `RefBExact`, `RefBExactLink`
- `LHSnippet`, `LMSnippet`
- `Status` (Pending/done/verified/rejected)
- `MatchType`, `DeterministicScore`, `MatchedWords`
- `fixed_by` and `fixed_at` (auto-populated when Status changes)

## Files

- `app.py` - FastAPI server
- `jsov-viewer.html` - Client UI (single-record, server-backed)
- `tmp_lh_links.json` - Primary dataset
- `data/` - Auxiliary reference data

## Hugging Face Deployment

This repository is configured for Hugging Face Spaces (Docker).
The metadata block at the top of this file is required by Spaces.

## Notes

- This project no longer supports local file upload in the client.
- All editing is server-driven to avoid concurrent misalignment.
