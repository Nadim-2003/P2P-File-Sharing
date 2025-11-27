# Setup Guide - P2P File-Sharing System

Complete step-by-step setup instructions for the P2P File-Sharing system.

## Prerequisites

### Windows
- Python 3.7 or higher
- Command Prompt or PowerShell
- Tkinter (included with Python on Windows)

### macOS/Linux
- Python 3.7 or higher
- Terminal
- Tkinter: `sudo apt-get install python3-tk` (Linux)

## Step 1: Verify Python Installation

### Windows (Command Prompt or PowerShell):
```bash
python --version
```

### macOS/Linux:
```bash
python3 --version
```

Expected output: `Python 3.x.x`

## Step 2: Check Tkinter Installation

### Windows:
```bash
python -m tkinter
```

A small window should appear if Tkinter is installed correctly.

### macOS/Linux:
```bash
python3 -m tkinter
```

## Step 3: Navigate to Project Directory

### Windows:
```bash
cd C:\Users\[YourUsername]\Documents\P2P-File-Sharing
```

### macOS/Linux:
```bash
cd ~/Documents/P2P-File-Sharing
```

## Step 4: Review Project Files

Verify all required files are present:

```
tracker/
  └── tracker_server.py      (Tracker implementation)
peer/
  └── peer_client.py         (Peer client with GUI)
shared/
  ├── __init__.py           (Module initializer)
  ├── utils.py              (Socket and message utilities)
  ├── chunking.py           (File chunking logic)
  └── chunks/               (Chunk storage - created automatically)
tests/
  ├── __init__.py           (Test module initializer)
  └── test_chunking.py      (Unit tests)
config.py                     (Configuration)
quick_start.py               (Quick start examples)
requirements.txt             (Dependencies - none!)
README_FULL.md              (Full documentation)
```

## Step 5: Optional - Run Quick Start Examples

### Windows:
```bash
python quick_start.py
```

### macOS/Linux:
```bash
python3 quick_start.py
```

This demonstrates:
- File chunking
- File utilities
- Message protocol

## Step 6: Run Tests (Optional)

### Windows:
```bash
python -m unittest tests.test_chunking -v
```

### macOS/Linux:
```bash
python3 -m unittest tests.test_chunking -v
```

Expected output shows all tests passing with ✓ marks.

## Starting the System

### Terminal 1: Start Tracker Server

**Windows:**
```bash
python tracker/tracker_server.py
```

**macOS/Linux:**
```bash
python3 tracker/tracker_server.py
```

Expected output:
```
2025-11-27 10:30:15,123 - INFO - Tracker Server started on 127.0.0.1:5000
```

### Terminal 2: Start First Peer Client

**Windows:**
```bash
python peer/peer_client.py
```

**macOS/Linux:**
```bash
python3 peer/peer_client.py
```

A GUI window appears with the peer client interface.

### Terminal 3+: Start Additional Peer Clients

Repeat the peer client command in new terminals to create more peers.

## First Test: Share a File

1. **On Peer 1 (Terminal 2):**
   - Click "Select File" button
   - Choose any file (e.g., a text file or image)
   - Click "Share" button
   - Wait for "Successfully shared file!" message
   - **Copy the File ID** displayed

2. **On Peer 2 (Terminal 3):**
   - Paste File ID in the "File ID:" field
   - Click "Download" button
   - Watch the status log
   - File appears in `downloads/` folder

3. **Success!**
   - Files should be identical
   - Check `downloads/` directory

## File Locations

After running:
- **Shared files**: `shared/chunks/{file_id}/chunk_*`
- **Downloaded files**: `downloads/`
- **Log output**: Console/Terminal

## Troubleshooting

### Python not found
**Windows:**
- Add Python to PATH: Settings → System → Advanced → Environment Variables
- Or use full path: `C:\Python39\python.exe`

### Tkinter not found
**Windows:**
- Reinstall Python with Tkinter selected
- During installation, check "tcl/tk and IDLE"

**Linux:**
```bash
sudo apt-get install python3-tk
```

**macOS:**
```bash
brew install python3-tk
```

### Port already in use
- Tracker Port 5000 in use: Change `TRACKER_PORT` in `config.py`
- Peer Port 6000 in use: Change `PEER_PORT` in `config.py`

### Connection refused
- Ensure tracker server is running first
- Check if ports are open (no firewall blocking)
- Verify IP addresses in configuration

### File not found on tracker
- Ensure peer server is running (should auto-start)
- Check tracker server status
- Verify network connectivity

## Performance Tips

1. **Large Files**: May take time to chunk/download
   - Monitor progress in status log
   - Larger chunks = fewer, but might miss more on error

2. **Multiple Peers**: Better for larger files
   - Each peer downloads different chunks
   - Distributes load

3. **Network**: Ensure good connectivity
   - Local network: Fast
   - Internet: May be slower

## Configuration Customization

Edit `config.py` to adjust:
- Tracker IP/Port
- Chunk size (default 256 KB)
- Download timeout
- Log level

## Next Steps

1. Test with different file types
2. Test with multiple peers
3. Monitor the status log
4. Try with large files (100+ MB)
5. Read `README_FULL.md` for detailed architecture

## Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| "Connection refused" | Start tracker server first |
| GUI doesn't open | Verify Tkinter installation |
| "Port in use" | Change port in config.py |
| Downloads incomplete | Ensure all peers are running |
| Files don't match | Check log for errors |

## Getting Help

1. Check console/terminal output for error messages
2. Read logs in status panel
3. Verify all services are running
4. Check network connectivity
5. Review README_FULL.md for architecture

## Success Indicators

✓ Tracker server running and listening on port 5000
✓ Peer clients showing unique peer IDs
✓ File ID displayed after sharing
✓ Status log showing chunk transfers
✓ Downloaded files in `downloads/` folder
✓ Files matching original after download

---

**You're all set! Start sharing files P2P!** 🚀
