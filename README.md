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
# Sefaria Fixes - JSON Link Viewer & Editor

A collaborative web application for reviewing and editing JSON link data with multi-user support.

**🚀 Live App:** https://dn-9281411-linking-lh.hf.space/

## Features

- 🔄 Real-time collaborative editing with conflict detection
- 👥 Multi-user support with change tracking
- 🔒 Simple authentication for upload/download
- 📝 Intuitive web interface for reviewing links
- 🚀 Deployed on Hugging Face Spaces

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

3. Open your browser to `http://localhost:7860`

### Environment Variables

- `ADMIN_USER`: Username allowed to upload/download files (default: `danny`)
- `PORT`: Server port (default: `7860`)

## Hugging Face Deployment

This app is configured for Hugging Face Spaces deployment.

### Required Files

The repository includes `HF_README.md` which should be renamed to `README.md` in your Hugging Face Space:

```yaml
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
```

### Manual Deployment

1. Create a new Space on Hugging Face (https://huggingface.co/new-space)
2. Choose "Docker" as the SDK
3. Clone your Space locally:
   ```bash
   git clone https://huggingface.co/spaces/dn-9281411/linking-lh
   ```
4. Copy the application files to the Space directory
5. Push to Hugging Face:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push
   ```

### GitHub to Hugging Face Sync

The repository automatically syncs to Hugging Face Spaces via GitHub Actions.

**Setup Instructions:**

1. Create a Hugging Face access token:
   - Go to https://huggingface.co/settings/tokens
   - Create a new token with `write` access

2. Add the token to GitHub Secrets:
   - Go to your GitHub repository settings
   - Navigate to Secrets and Variables → Actions
   - Create a new secret named `HF_TOKEN`
   - Paste your Hugging Face token

3. Push to main branch - the workflow will automatically sync to Hugging Face

## API Endpoints

### Public Endpoints

- `GET /` - Web interface
- `GET /data` - Get current data (with version info)
- `GET /version` - Get current data version
- `POST /save` - Save changes (requires username header)
- `GET /health` - Health check

### Admin-Only Endpoints (requires ADMIN_USER)

- `POST /upload` - Upload new JSON file
- `GET /download` - Download current JSON file

### Usage with Authentication

All requests should include the username header:

```bash
curl -H "X-Username: yourname" http://localhost:7860/data
```

## Multi-User Support

The application supports concurrent editing by multiple users:

- Each save includes a version hash
- Conflicts are detected automatically
- Users are prompted to reload if data changed
- `fixed_by` field tracks who made changes

## Data Structure

Each item should have the following fields:

- `RefA`, `RefALink` - Reference A and its link
- `RefB`, `RefBLink`, `RefBExact`, `RefBExactLink` - Reference B details
- `RefBExcerpt` - Text excerpt from Reference B
- `Snippet` - Text snippet from Likutei Halakhot
- `Status` - Current status (Pending/done/verified/rejected)
- `MatchType`, `DeterministicScore`, `MatchedWords` - Matching metadata
- `fixed_by` - Username who last changed the status (auto-populated)
- `fixed_at` - Timestamp of last status change (auto-populated)

## License

MIT

Find typos in Sefaria

## 1st version
Find end letters that appear in the middle of a word.

## JSON Link Viewer & Editor

An interactive web-based tool for reviewing and editing JSON link data between Likutei Halakhot and Likutei Moharan.

### Features

- **Two-column layout** comparing source (RefA) and target (RefB) references
- **Editable fields**: Snippet, RefBExact, Status, LLM fields
- **Navigation**: Previous/Next buttons, Go to item number
- **Filtering**: Filter by Status and/or LLM Status
- **Direct file editing**: Save changes directly to the original JSON file (no downloads)
- **Auto-backup**: Creates `.backup` files before each save
- **Keyboard shortcuts**:
  - `Ctrl/Cmd + ←/→`: Navigate items
  - `Ctrl/Cmd + S`: Save
  - `Ctrl/Cmd + G`: Focus on Go to input

### Usage

#### With Local Server (Recommended - Direct File Editing)

1. Start the server:
   ```bash
   python json-viewer-server.py tmp_lh_links.json
   ```

2. Open in browser:
   ```
   http://localhost:8000
   ```

3. Edit and save - changes save directly to the file!

#### Standalone Mode (File Upload/Download)

1. Open `json-viewer.html` directly in your browser
2. Click "📁 בחר קובץ JSON" to upload your JSON file
3. Make edits
4. Click "שמור שינויים" to download the updated file

### File Structure

- `json-viewer.html` - The interactive viewer/editor interface
- `json-viewer-server.py` - Local Python server for direct file editing
- `tmp_lh_links.json` - JSON data file with link references

