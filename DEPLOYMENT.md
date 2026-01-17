# Deployment & Setup Guide

## Quick Start (Local)

```bash
./start.sh
```

Or manually:

```bash
pip install -r requirements.txt
python app.py
```

Access at: http://localhost:7860

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_USER` | `danny` | Username allowed to upload/download files |
| `PORT` | `7860` | Server port |

## GitHub to Hugging Face Sync

### One-Time Setup

1. **Create Hugging Face Token**
   - Visit: https://huggingface.co/settings/tokens
   - Create token with **write** access
   - Copy the token

2. **Add to GitHub Secrets**
   - Go to: `https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions`
   - Click "New repository secret"
   - Name: `HF_TOKEN`
   - Value: (paste your HF token)
   - Click "Add secret"

3. **Enable GitHub Actions**
   - Go to: `https://github.com/YOUR_USERNAME/YOUR_REPO/actions`
   - If needed, enable workflows

### Automatic Deployment

Every push to `main` or `master` branch will automatically sync to Hugging Face:

```bash
git add .
git commit -m "Update application"
git push origin main
```

The GitHub Action (`.github/workflows/sync-to-hf.yml`) will automatically:
1. Checkout your code
2. Push to Hugging Face Space
3. Trigger rebuild on Hugging Face

### Manual Trigger

You can also manually trigger the sync:
1. Go to Actions tab in GitHub
2. Select "Sync to Hugging Face" workflow
3. Click "Run workflow"

## Hugging Face Space Setup

### Initial Setup

1. Create Space: https://huggingface.co/new-space
   - Name: `linking-lh`
   - SDK: Docker
   - Make it Public or Private

2. The space will use:
   - `Dockerfile` for container setup
   - `app.py` as the main application
   - `requirements.txt` for dependencies
   - Port 7860 (configured in Dockerfile and app)

3. Copy `HF_README.md` content to your Space's `README.md`

### Persistent Data

⚠️ **Important**: Hugging Face Spaces are ephemeral by default!

To persist data across rebuilds:
1. Enable Persistent Storage in Space settings
2. Or use Hugging Face Datasets for data storage

## Multi-User Features

### Concurrent Editing
- ✅ Multiple users can edit simultaneously
- ✅ Conflict detection prevents data loss
- ✅ Auto-reload on conflict
- ✅ Version tracking with hash-based detection

### Change Tracking
- ✅ `fixed_by` field auto-populated on status change
- ✅ `fixed_at` timestamp added
- ✅ Username displayed in header

### File Locking
- ✅ Uses `filelock` for safe concurrent writes
- ✅ Atomic operations
- ✅ No race conditions

## API Usage Examples

### Get Data
```bash
curl -H "X-Username: john" http://localhost:7860/data
```

### Save Changes
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Username: john" \
  -H "X-Data-Version: abc123..." \
  -d @data.json \
  http://localhost:7860/save
```

### Upload (Admin Only)
```bash
curl -X POST \
  -H "X-Username: danny" \
  -F "file=@new_data.json" \
  http://localhost:7860/upload
```

### Download (Admin Only)
```bash
curl -H "X-Username: danny" \
  http://localhost:7860/download \
  -o backup.json
```

## Troubleshooting

### Port Already in Use
```bash
export PORT=8080
python app.py
```

### Permission Denied on Upload
- Ensure `X-Username` header matches `ADMIN_USER`
- Check environment variable: `echo $ADMIN_USER`

### Conflict Errors
- This is expected when multiple users edit the same item
- Click OK to reload fresh data
- Make your changes again

### GitHub Sync Not Working
1. Check secret exists: GitHub repo → Settings → Secrets
2. Check workflow runs: GitHub repo → Actions
3. Verify HF_TOKEN has write permissions
4. Check workflow logs for errors

## Production Checklist

- [ ] Set `ADMIN_USER` environment variable
- [ ] Add `HF_TOKEN` to GitHub secrets
- [ ] Test upload/download functionality
- [ ] Verify multi-user editing works
- [ ] Enable persistent storage (if needed)
- [ ] Configure monitoring/logging
- [ ] Set up backup strategy

## Support

For issues:
1. Check application logs
2. Verify environment variables
3. Test API endpoints with curl
4. Check GitHub Actions workflow logs
