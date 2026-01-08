# P2P File Sharing System

A modern, BitTorrent-like peer-to-peer file sharing application with a clean uTorrent-style GUI interface.

## 🌟 Features

### Core Functionality
- **Decentralized File Sharing**: Share and download files directly between peers
- **Chunk-based Transfer**: Files are split into chunks for efficient parallel downloading
- **Persistent Peer Identity**: Unique peer ID maintained across sessions (like qBittorrent)
- **Automatic State Management**: Resume downloads and continue seeding after restarts
- **Multi-peer Support**: Run multiple peer instances on different ports

### Modern GUI Interface
- **Dashboard**: Overview of all torrents with real-time statistics
- **Active Downloads**: Live progress tracking with ETA calculation
- **Download History**: Track all completed and failed downloads
- **Share Files**: Easy file sharing with visual feedback
- **Statistics**: Detailed transfer logs and performance metrics

### Advanced Features
- **Pause/Resume Downloads**: Full control over active downloads
- **Auto-share Downloaded Files**: Optionally share completed downloads
- **Peer Discovery**: Automatic peer tracking via central tracker
- **Upload/Download Speed Monitoring**: Real-time transfer statistics
- **Smart Caching**: Efficient peer count and file metadata caching

## 📋 Requirements

### System Requirements
- Python 3.7 or higher
- Windows/Linux/macOS
- Network connectivity for peer-to-peer transfers

### Python Dependencies
```
tkinter (usually comes with Python)
```

No additional packages required! All dependencies are Python standard library.

## 🚀 Quick Start

### 1. Installation

Clone or download this repository:
```bash
git clone <repository-url>
cd P2P-File-Sharing
```

### 2. Start the Tracker Server

The tracker coordinates peer discovery. Start it first:

```bash
python tracker/tracker_server.py
```

**Default tracker address**: `192.168.0.202:5000`

To change the tracker IP, edit `TRACKER_HOST` in:
- `tracker/tracker_server.py` (line ~15)
- `peer/peer_client.py` (line ~48)

### 3. Start Peer Client(s)

#### Single Peer:
```bash
python peer/peer_client.py
```

#### Multiple Peers (for testing):
```bash
python launch_multiple_peers.py
```

Or use the batch file on Windows:
```bash
start_peer.bat
```

## 📖 User Guide

### Dashboard Tab
The main view showing all your torrents (shared and downloading files):
- **Name**: Filename
- **Size**: File size in KB/MB/GB
- **Done**: Download progress percentage
- **Status**: Seeding, Downloading, Finished
- **Seeds/Peers**: Number of seeders and leechers
- **Down Speed/Up Speed**: Current transfer rates

**Statistics Panel** (top):
- **Peer Info**: Your peer ID and port
- **Uploaded**: Number of files shared + total data uploaded (MB/GB)
- **Downloaded**: Number of completed downloads + total data downloaded (MB/GB)
- **Current Speeds**: Real-time upload and download speeds

### Share Files Tab
Share files with the network:

1. Click **"Add File"** to select a file from your computer
2. Click **"Share"** to make it available to other peers
3. File is automatically split into chunks and registered with tracker
4. View all shared files with their upload statistics

**Columns**:
- File ID (first 8 characters for identification)
- Progress (100% for complete files)
- Role (SEEDER/LEECHER)
- Seeders/Leechers count
- Upload speed

### Download Tab

#### Search & Download:
1. **Search by filename** or **file ID**
2. Select a file from search results
3. Click **"Download Selected"**
4. Monitor progress in Active Downloads section

#### Active Downloads:
Real-time view of ongoing downloads with:
- **Progress**: Percentage completed
- **Status**: Downloading, Paused, Completed, Failed
- **Seeds/Peers**: Available sources
- **Down Speed**: Current download rate
- **ETA**: Estimated time remaining

**Controls**:
- **⏸ Pause**: Pause the selected download
- **▶ Resume**: Resume a paused download
- **✖ Cancel**: Cancel the download

#### Download History:
Track all your download activity:
- Completed downloads (100% progress)
- Failed downloads with error details
- Original download speeds
- Current seed/peer availability

**Filter**: Search downloads by filename

### Statistics Tab
Detailed transfer logs showing:
- Transfer type (UPLOAD/DOWNLOAD)
- Peer addresses
- File IDs
- Chunk numbers
- Bytes transferred
- Timestamps

## ⚙️ Configuration

### Network Settings

**For Multi-Computer Setup:**

1. Find your local IP address:
   ```bash
   python network_setup.py
   ```

2. Update `TRACKER_HOST` in both files to your tracker server's IP:
   - `tracker/tracker_server.py`
   - `peer/peer_client.py`

### Port Configuration

**Tracker Port**: Default `5000`
- Change in `tracker/tracker_server.py`: `TRACKER_PORT`

**Peer Ports**: Default range `6000-6100`
- Change in `peer/peer_client.py`: `PEER_PORT_START` and `PEER_PORT_END`

### File Storage Locations

**Downloads**: `./downloads/` - All downloaded files
**Shared**: `./shared/` - Original shared files  
**Chunks**: `./shared/chunks/` - File chunks for sharing
**State**: `./peer_state/` - Persistent peer state and history

## 🏗️ Architecture

### System Components

```
┌─────────────────┐
│  Tracker Server │  (Coordinates peers, tracks files)
│   Port: 5000    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼───┐
│ Peer │  │ Peer │  (Share & download files)
│ 6001 │  │ 6002 │
└──────┘  └──────┘
```

### File Structure

```
P2P-File-Sharing/
├── peer/
│   └── peer_client.py          # Main peer client with GUI
├── tracker/
│   └── tracker_server.py       # Central tracker server
├── shared/
│   ├── utils.py                # Network utilities
│   ├── chunking.py             # File chunking logic
│   └── __init__.py
├── peer_identity.py            # Persistent peer ID management
├── state_manager.py            # State persistence
├── config.py                   # Configuration
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

### Key Technologies

- **Tkinter + ttk**: Modern GUI interface
- **Socket Programming**: Direct peer-to-peer communication
- **Threading**: Concurrent downloads and UI updates
- **JSON**: State persistence and message protocol
- **SHA256 Hashing**: File identification
- **Chunking**: Parallel transfer optimization

## 🔧 Technical Details

### File Transfer Protocol

1. **File Registration**: Peer splits file into chunks and registers with tracker
2. **Peer Discovery**: Tracker returns list of peers with the file
3. **Chunk Download**: Parallel download of chunks from multiple peers
4. **Verification**: SHA256 hash verification
5. **Assembly**: Chunks merged into complete file
6. **Seeding**: Completed files automatically available for upload

### Chunk Size
- Default: **256 KB** (262,144 bytes)
- Configurable in `peer/peer_client.py`: `CHUNK_SIZE`

### State Management
Automatically saves:
- Shared files (torrents)
- Download history
- Peer role (seeder/leecher)
- Download progress
- Statistics

State persists across restarts in `peer_state/peer_<id>_port_<port>.json`

## 🎯 Use Cases

### Single Computer Testing
1. Start tracker
2. Launch multiple peer instances on different ports
3. Share file from one peer
4. Download from another peer

### Multi-Computer Network
1. Start tracker on one computer (note its IP)
2. Update `TRACKER_HOST` on all computers
3. Start peer clients on each computer
4. Share and download files across the network

### Private File Sharing
- No internet connection required
- Local network only (LAN)
- Direct peer-to-peer transfers
- No central file storage

## 📊 Statistics & Monitoring

### Real-time Metrics
- **Upload Speed**: KB/s (live)
- **Download Speed**: KB/s (live)
- **Total Uploaded**: MB/GB (cumulative)
- **Total Downloaded**: MB/GB (cumulative)
- **Files Shared**: Count
- **Files Downloaded**: Count

### Transfer Logs
- Every chunk upload/download logged
- Timestamp, peer, file ID, chunk number
- Transfer size in KB

## 🐛 Troubleshooting

### Connection Issues
**Problem**: Can't find tracker or peers

**Solutions**:
1. Verify tracker is running: `python tracker/tracker_server.py`
2. Check firewall settings (allow Python)
3. Verify IP addresses in config
4. Ensure all devices on same network

### Download Stuck
**Problem**: Download not progressing

**Solutions**:
1. Check if seeders are online (Seeds column)
2. Try pausing and resuming
3. Check network connectivity
4. Restart peer client

### Files Not Showing
**Problem**: Shared files don't appear

**Solutions**:
1. Verify file was chunked (check `shared/chunks/<file_id>/`)
2. Confirm tracker registration (see peer logs)
3. Wait 10 seconds for peer count cache update
4. Restart peer client to reload state

## 🔒 Security Notes

- No encryption implemented (files transferred in plain text)
- Suitable for trusted networks only
- Peer IDs are persistent but not authenticated
- No user authentication system

## 🚀 Performance Tips

1. **Parallel Downloads**: Max 5 chunks simultaneously (configurable)
2. **Update Frequency**: Staggered UI updates to prevent flickering
3. **Caching**: Peer counts cached for 10 seconds
4. **Smart Updates**: Only refresh UI when data changes

## 📝 License

This project is provided as-is for educational purposes.

## 🤝 Contributing

This is a demonstration project. Feel free to fork and modify for your needs.

## 📞 Support

For issues or questions:
1. Check this README
2. Review console logs for error messages
3. Verify network configuration
4. Ensure all dependencies installed

---

**Built with Python & Tkinter** | Modern P2P File Sharing Made Simple
