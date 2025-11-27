# P2P File-Sharing System - Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Quick Start](#quick-start)
5. [Usage Guide](#usage-guide)
6. [Technical Details](#technical-details)
7. [API Reference](#api-reference)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The P2P File-Sharing System is a complete peer-to-peer file distribution platform built with Python. It allows multiple users (peers) to share files with each other through a centralized tracker that coordinates file availability.

### Key Characteristics
- **Decentralized**: Files are stored on peer machines, not central server
- **Efficient**: Files split into chunks, downloaded in parallel from multiple peers
- **Reliable**: TCP ensures data integrity
- **User-Friendly**: GUI for easy file sharing and downloading
- **Lightweight**: No external dependencies, pure Python

---

## Architecture

### System Components

```
┌────────────────────────────────────────────────────────────┐
│                    P2P File-Sharing System                 │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                   Centralized Tracker                      │
│  • Maintains file metadata                                 │
│  • Maps file IDs to peer addresses                         │
│  • Responds to peer queries                                │
│  • Handles peer registration                               │
│  • Port: 5000 (TCP)                                        │
└────────────────────────────────────────────────────────────┘
              ↑              ↑              ↑
              │ Register/    │ Query        │
              │ Query        │              │
      ┌──────┴──────────┬───┴──────────┬───┴──────────┐
      │                 │              │              │
      v                 v              v              v
  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │   Peer 1    │ │   Peer 2     │ │   Peer 3     │ │   Peer 4     │
  │  Port 6000  │ │  Port 6001   │ │  Port 6002   │ │  Port 6003   │
  ├─────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
  │ • GUI       │ │ • GUI        │ │ • GUI        │ │ • GUI        │
  │ • Chunker   │ │ • Chunker    │ │ • Chunker    │ │ • Chunker    │
  │ • Server    │ │ • Server     │ │ • Server     │ │ • Server     │
  │ • Storage   │ │ • Storage    │ │ • Storage    │ │ • Storage    │
  └─────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
      ↑───────────────────↑─────────────────┬──────────────────↑
      │   CHUNK_REQUEST   │                 │                  │
      │   Binary Data     │                 │                  │
      └───────────────────┘─────────────────┴──────────────────┘
```

### Data Flow: Sharing a File

```
1. User selects file (e.g., movie.mp4)
   │
   ├─→ Calculate SHA256 hash → File ID
   │
   ├─→ Split into chunks (256 KB each)
   │   • chunk_0 (256 KB)
   │   • chunk_1 (256 KB)
   │   • ...
   │   • chunk_N (remaining bytes)
   │
   ├─→ Register with Tracker
   │   {
   │     "type": "REGISTER",
   │     "file_id": "abc123...",
   │     "filename": "movie.mp4",
   │     "num_chunks": 42,
   │     "peer_id": "peer001",
   │     "host": "192.168.1.100",
   │     "port": 6000
   │   }
   │
   └─→ Ready for other peers to download!
```

### Data Flow: Downloading a File

```
1. User enters File ID
   │
   ├─→ Query Tracker for file info
   │   {
   │     "type": "QUERY",
   │     "file_id": "abc123..."
   │   }
   │
   ├─→ Receive peer list (who has this file)
   │   [
   │     {"host": "192.168.1.100", "port": 6000},
   │     {"host": "192.168.1.101", "port": 6001},
   │     ...
   │   ]
   │
   ├─→ Request chunks from multiple peers in parallel
   │   For chunk_0: Request from Peer 1
   │   For chunk_1: Request from Peer 2
   │   For chunk_2: Request from Peer 1
   │   ...
   │
   ├─→ Receive binary chunk data
   │
   ├─→ Save chunks locally
   │
   ├─→ Merge chunks into original file
   │   chunk_0 + chunk_1 + ... + chunk_N = movie.mp4
   │
   └─→ Save to downloads/ folder!
```

---

## Components

### 1. Tracker Server (`tracker/tracker_server.py`)

**Purpose**: Central coordinator that maintains file metadata and peer mappings.

**Responsibilities**:
- Accept connections from peers
- Register files when peers share them
- Query peer list for specific files
- Remove peers from file lists (unregister)

**Key Classes**:
- `TrackerServer`: Main server class
  - `start()`: Start listening for connections
  - `handle_client()`: Handle individual peer connections
  - `process_message()`: Route messages to handlers
  - `handle_register()`: Process file registration
  - `handle_query()`: Process file queries
  - `handle_unregister()`: Process peer unregistration
  - `get_stats()`: Get server statistics

**Data Structure**:
```python
{
  "file_id": {
    "filename": "movie.mp4",
    "num_chunks": 42,
    "peers": [
      {"host": "192.168.1.100", "port": 6000, "peer_id": "p1"},
      {"host": "192.168.1.101", "port": 6001, "peer_id": "p2"},
      ...
    ]
  }
}
```

### 2. Peer Client (`peer/peer_client.py`)

**Purpose**: User-facing application with GUI and P2P capabilities.

**Responsibilities**:
- Display GUI for user interactions
- Share files with the P2P network
- Download files from other peers
- Run local server to serve chunks

**Key Classes**:
- `PeerServer`: Server component that serves chunks
  - `start()`: Start in background thread
  - `_run_server()`: Main server loop
  - `_handle_chunk_request()`: Handle chunk requests

- `PeerClient`: GUI and main client logic
  - `_select_file_to_share()`: File selection dialog
  - `_share_file()`: Share file process
  - `_download_file()`: Download file process
  - `_register_file()`: Register with tracker
  - `_query_tracker()`: Query for peers
  - `_download_chunk()`: Download single chunk

### 3. Chunking Module (`shared/chunking.py`)

**Purpose**: Handle file splitting and merging.

**Responsibilities**:
- Split large files into fixed-size chunks
- Merge chunks back into original files
- Verify chunk integrity
- Manage chunk storage

**Key Classes**:
- `FileChunker`: File chunking operations
  - `split_file()`: Split into chunks
  - `merge_chunks()`: Merge chunks into file
  - `get_chunk()`: Read specific chunk
  - `save_chunk()`: Save chunk to disk
  - `verify_chunks()`: Verify all chunks exist
  - `get_total_size()`: Get total chunk size

### 4. Utilities Module (`shared/utils.py`)

**Purpose**: Common utilities for socket and message handling.

**Key Classes**:
- `SocketUtils`: Socket operations
  - `send_message()`: Send JSON message
  - `receive_message()`: Receive JSON message
  - `send_chunk_data()`: Send binary data
  - `receive_chunk_data()`: Receive binary data
  - `connect_to_server()`: Create connection

- `FileUtils`: File operations
  - `validate_chunk_size()`: Validate chunk size
  - `calculate_num_chunks()`: Calculate chunk count
  - `get_file_size()`: Get file size

- `MessageBuilder`: Protocol message construction
  - `register_message()`: Build REGISTER message
  - `query_message()`: Build QUERY message
  - `chunk_request_message()`: Build CHUNK_REQUEST
  - `chunk_response_message()`: Build CHUNK_RESPONSE

---

## Quick Start

### 1. Start Tracker Server
```bash
python tracker/tracker_server.py
```

### 2. Start First Peer
```bash
python peer/peer_client.py
```

### 3. Start Second Peer (in new terminal)
```bash
python peer/peer_client.py
```

### 4. Share File
- On first peer: Select file → Share
- Copy File ID

### 5. Download File
- On second peer: Enter File ID → Download

---

## Usage Guide

### Sharing a File

1. **Select File**:
   - Click "Select File" button
   - Choose file from computer

2. **Share**:
   - Click "Share" button
   - Application processes:
     - Calculates SHA256 hash (File ID)
     - Splits into 256 KB chunks
     - Registers with tracker
   - Status shows: "File shared successfully!"
   - File ID displayed for sharing

3. **Share File ID**:
   - Copy displayed File ID
   - Share with others (email, chat, etc.)

### Downloading a File

1. **Get File ID**:
   - Receive File ID from file owner

2. **Enter File ID**:
   - Paste into "File ID:" field

3. **Download**:
   - Click "Download" button
   - Status log shows progress:
     - Querying tracker
     - Downloading chunks
     - Merging chunks
   - File saved to `downloads/` folder

### Monitoring Progress

- **Status Log**: Shows real-time operations
- **Console**: Detailed logging information
- **File System**: Check `downloads/` for completed files

---

## Technical Details

### File ID Generation

File ID is SHA256 hash of file contents (first 16 characters):
```
Original file: movie.mp4 (1 GB)
SHA256 hash: a1b2c3d4e5f6g7h8j9k0l1m2n3o4p5q6...
File ID: a1b2c3d4e5f6g7h8 (first 16 chars)
```

### Chunk Storage

Chunks stored locally with structure:
```
shared/
├── chunks/
│   ├── file_id_1/
│   │   ├── chunk_0
│   │   ├── chunk_1
│   │   ├── chunk_2
│   │   └── ...
│   ├── file_id_2/
│   │   ├── chunk_0
│   │   ├── chunk_1
│   │   └── ...
│   └── ...
```

### Chunk Size Impact

- **256 KB (default)**:
  - 1 MB file = 4 chunks
  - 1 GB file = 4096 chunks
  - Balanced for most use cases

- **Larger chunks** (512 KB):
  - Fewer chunks to manage
  - Larger transfer units
  - More data loss if connection fails

- **Smaller chunks** (64 KB):
  - More chunks to manage
  - Smaller transfer units
  - Less data loss per failure

### Network Protocol

**TCP Communication**:
- JSON messages for metadata
- Binary data for chunks
- No UDP (ensures reliability)

**Message Format**:
```
[JSON Length: 4 bytes][JSON Data][Binary Data (if chunk)]
```

### Threading Model

- **Tracker**: One thread per peer connection
- **Peer Server**: One thread per chunk request
- **Peer Client**: Background threads for I/O operations
  - File sharing thread
  - Each chunk download in thread

### Error Handling

- **Connection Failures**: Retry with next peer
- **Timeout**: Configure in `DOWNLOAD_TIMEOUT`
- **Missing Chunks**: Download from backup peers
- **Corrupted Data**: None (TCP ensures integrity)

---

## API Reference

### TrackerServer API

```python
from tracker.tracker_server import TrackerServer

# Create and start tracker
tracker = TrackerServer(host='127.0.0.1', port=5000)
tracker.start()

# Get statistics
stats = tracker.get_stats()
# Returns:
# {
#   'total_files': 5,
#   'total_peers': 12,
#   'files': {...}
# }
```

### FileChunker API

```python
from shared.chunking import FileChunker

chunker = FileChunker(chunk_size=262144)

# Split file
num_chunks = chunker.split_file('input.mp4', 'chunks_dir/')

# Merge file
success = chunker.merge_chunks('chunks_dir/', 'output.mp4', num_chunks)

# Get chunk
chunk_data = chunker.get_chunk('chunks_dir/', chunk_index=0)

# Verify
verified = chunker.verify_chunks('chunks_dir/', num_chunks)
```

### SocketUtils API

```python
from shared.utils import SocketUtils

# Connect to server
sock = SocketUtils.connect_to_server('127.0.0.1', 5000)

# Send message
SocketUtils.send_message(sock, {"type": "QUERY"})

# Receive message
msg = SocketUtils.receive_message(sock, timeout=5.0)

# Send chunk
SocketUtils.send_chunk_data(sock, chunk_bytes)

# Receive chunk
data = SocketUtils.receive_chunk_data(sock, size=262144, timeout=5.0)
```

### MessageBuilder API

```python
from shared.utils import MessageBuilder

# Build messages
register = MessageBuilder.register_message(
    "file_id", "filename.txt", 5, "peer1", "192.168.1.1", 6000
)

query = MessageBuilder.query_message("file_id")

chunk_req = MessageBuilder.chunk_request_message("file_id", 0)

chunk_resp = MessageBuilder.chunk_response_message(
    "file_id", 0, 262144, "success"
)
```

---

## Troubleshooting

### Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection refused | Tracker not running | Start tracker first |
| Port in use | Port already taken | Change port in config.py |
| GUI doesn't open | Tkinter missing | Install tkinter |
| File not found | Not registered | Share file again |
| Download incomplete | Peer offline | Ensure all peers running |
| Slow download | Network/CPU | Check system resources |
| Large file memory | Too many chunks | Reduce chunk size |

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Errors

**"OSError: [Errno 48] Address already in use"**
```bash
# Find and kill process using port 5000
# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :5000
kill -9 <PID>
```

**"ModuleNotFoundError: No module named 'shared'"**
- Ensure running from project root
- Check `shared/__init__.py` exists

**"File already exists" during download**
- Downloaded file conflicts with existing
- Delete or rename existing file
- Or change `DOWNLOADS_DIRECTORY`

---

## Performance Optimization

### Recommended Settings

- **LAN (fast network)**:
  - Chunk size: 512 KB
  - Timeout: 5 seconds
  - Buffer: 8 KB

- **Internet (slow network)**:
  - Chunk size: 256 KB
  - Timeout: 30 seconds
  - Buffer: 4 KB

- **Large files (>500 MB)**:
  - Multiple peers: 3+
  - Chunk size: 256 KB
  - Concurrent: 5+

### Monitoring

Check status log for:
- Chunk download times
- Peer count per file
- Registration success
- Error rates

---

## Future Enhancements

1. **DHT (Distributed Hash Table)**: Remove tracker dependency
2. **Encryption**: Secure file transfers
3. **Compression**: Reduce bandwidth
4. **Resume**: Continue broken downloads
5. **Search**: Find files by name
6. **Authentication**: User accounts
7. **Bandwidth Limiting**: Control speeds
8. **NAT Traversal**: Work behind firewalls

---

## Contributing

Ideas for improvement:
- Add new features
- Improve UI/UX
- Optimize performance
- Add documentation
- Report bugs

---

**Happy P2P Sharing!** 🚀
