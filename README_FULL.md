# P2P File-Sharing System

A lightweight peer-to-peer (P2P) file-sharing application built with Python, featuring a centralized tracker server, GUI-based peer clients, and efficient chunk-based file distribution.

## Features

### 1. Tracker Server
- **Lightweight Design**: Maintains mappings between file IDs and available peers
- **Peer Registration**: Handles peer registration for shared files
- **Query Support**: Responds to peer queries for file availability
- **Metadata Tracking**: Stores file ID, number of chunks, and peer addresses
- **Thread-Safe Operations**: Uses locks for concurrent access

### 2. Peer Client with GUI (Tkinter)
- **File Sharing**: Share files by selecting and uploading them
- **File Downloading**: Download files using file IDs from other peers
- **Status Display**: Real-time status messages and download progress
- **User-Friendly Interface**: Intuitive buttons and controls
- **Local Peer Server**: Built-in server to serve chunks to other peers

### 3. File Chunking and Merging
- **Fixed-Size Chunks**: Default 256 KB chunks (configurable)
- **Automatic Splitting**: Splits files into manageable chunks
- **Sequential Merging**: Reconstructs original files from chunks
- **Chunk Verification**: Ensures all chunks are received

### 4. Multi-Peer Downloading
- **Parallel Downloads**: Fetch chunks from multiple peers simultaneously
- **Load Distribution**: Different chunks downloaded from different peers
- **Fault Tolerance**: Automatically retry if a peer fails
- **Timeout Handling**: Configurable timeouts for chunk transfers

### 5. Reliable TCP Communication
- **TCP Sockets**: Ensures reliable data transfer
- **JSON Messaging**: Protocol messages encoded in JSON
- **Binary Chunk Transfer**: Efficient binary data transmission
- **Error Handling**: Comprehensive error checking and recovery

## Project Structure

```
P2P-File-Sharing/
├── README.md                    # Overview
├── tracker/
│   └── tracker_server.py       # Tracker server implementation
├── peer/
│   └── peer_client.py          # Peer client with GUI
├── shared/
│   ├── utils.py                # Shared utilities (socket, messaging)
│   ├── chunking.py             # File chunking and merging
│   └── chunks/                 # Local chunk storage directory
├── downloads/                   # Downloaded files directory
└── tests/
    └── test_chunking.py        # Unit tests for chunking
```

## Installation

### Prerequisites
- Python 3.7 or higher
- Tkinter (usually comes with Python)
- No external dependencies required!

### Setup

1. Navigate to project directory:
   ```bash
   cd P2P-File-Sharing
   ```

2. Verify Python installation:
   ```bash
   python --version
   ```

3. Directories are created automatically by the application

## Usage

### Step 1: Start the Tracker Server

Open terminal and run:
```bash
python tracker/tracker_server.py
```

Expected output:
```
2025-11-27 10:30:15,123 - INFO - Tracker Server started on 127.0.0.1:5000
```

### Step 2: Start Peer Clients

Open new terminal windows and run:
```bash
python peer/peer_client.py
```

You can start multiple instances for testing P2P functionality.

### Step 3: Use the GUI

#### To Share a File:
1. Click "Select File" button
2. Choose a file from your system
3. Click "Share" button
4. Copy the displayed File ID

#### To Download a File:
1. Obtain File ID from another peer
2. Enter File ID in input field
3. Click "Download" button
4. File saves to `downloads/` directory

## Configuration

### Tracker Server (`tracker/tracker_server.py`)
```python
TRACKER_HOST = '127.0.0.1'    # Tracker server IP
TRACKER_PORT = 5000            # Tracker server port
```

### Peer Client (`peer/peer_client.py`)
```python
TRACKER_HOST = '127.0.0.1'    # Tracker server IP
TRACKER_PORT = 5000            # Tracker server port
PEER_PORT = 6000               # Peer server port
CHUNK_SIZE = 262144            # Chunk size (256 KB)
DOWNLOAD_TIMEOUT = 10.0        # Timeout in seconds
```

## Protocol Messages

### REGISTER - Share a File
```json
{
  "type": "REGISTER",
  "file_id": "abc123def456",
  "filename": "document.pdf",
  "num_chunks": 5,
  "peer_id": "peer-001",
  "host": "192.168.1.100",
  "port": 6000
}
```

### QUERY - Request File Info
```json
{
  "type": "QUERY",
  "file_id": "abc123def456"
}
```

### CHUNK_REQUEST - Download Chunk
```json
{
  "type": "CHUNK_REQUEST",
  "file_id": "abc123def456",
  "chunk_index": 0
}
```

## Running Tests

```bash
python -m unittest tests.test_chunking -v
```

### Test Coverage
- File splitting and merging
- Chunk storage and retrieval
- Large file handling (1 MB+)
- Message building
- File utilities

## Quick Example

1. **Terminal 1 - Start Tracker:**
   ```bash
   python tracker/tracker_server.py
   ```

2. **Terminal 2 - Start Peer 1:**
   ```bash
   python peer/peer_client.py
   ```

3. **Terminal 3 - Start Peer 2:**
   ```bash
   python peer/peer_client.py
   ```

4. **In Peer 1 GUI:**
   - Click "Select File" → Choose a file
   - Click "Share"
   - Copy the File ID

5. **In Peer 2 GUI:**
   - Enter the File ID
   - Click "Download"
   - File appears in `downloads/` folder

## System Architecture

```
┌─────────────────────────┐
│   Tracker Server        │
│   (Port 5000)           │
│  - File Metadata        │
│  - Peer Mappings        │
└────────────┬────────────┘
             │
     ┌───────┼───────┐
     │       │       │
     v       v       v
 ┌────────┐┌────────┐┌────────┐
 │ Peer 1 ││ Peer 2 ││ Peer 3 │
 │ :6000  ││ :6001  ││ :6002  │
 │  GUI   ││  GUI   ││  GUI   │
 └────────┘└────────┘└────────┘
     ↑───────────────────────↑
     └─ P2P Chunk Transfer ─┘
```

## How It Works

### Sharing a File:
1. User selects a file
2. Application calculates SHA256 hash as File ID
3. File is split into 256 KB chunks
4. Chunks stored in `shared/chunks/{file_id}/`
5. File metadata registered with tracker
6. Tracker stores file info and peer address

### Downloading a File:
1. User enters File ID
2. Application queries tracker for file info
3. Tracker returns list of peers with the file
4. Application downloads chunks from available peers
5. Chunks saved locally as `chunk_0`, `chunk_1`, etc.
6. Chunks merged back into original file
7. File saved to `downloads/` directory

### Multi-Peer Optimization:
- Different chunks downloaded from different peers simultaneously
- If a peer fails, another peer is tried
- Timeout handling prevents hanging connections
- Load is distributed across peers

## Key Technologies

- **Python 3.7+**: Core language
- **Tkinter**: GUI framework (built-in)
- **TCP Sockets**: Network communication
- **Threading**: Concurrent operations
- **JSON**: Message protocol
- **SHA256**: File hashing

## Features Implemented

✅ Tracker Server with peer mapping
✅ Tkinter GUI for peer client
✅ File chunking (256 KB default)
✅ File merging
✅ Multi-peer downloading
✅ TCP socket communication
✅ JSON message protocol
✅ Thread-safe operations
✅ Comprehensive error handling
✅ Unit tests
✅ Logging system
✅ Status display

## Troubleshooting

**Connection refused?**
- Ensure tracker server is running
- Check if port 5000 is available

**File not found?**
- Verify file was registered successfully
- Check file ID is correct

**Download incomplete?**
- Ensure source peer is still running
- Check network connectivity

**GUI unresponsive?**
- Downloads run in background threads
- Check status log for progress

## Performance Characteristics

- **Chunk Size**: 256 KB (tunable)
- **Max Connections**: 5+ per peer
- **Transfer Timeout**: 10 seconds
- **Socket Buffer**: 4 KB

## Future Enhancements

- DHT for decentralized tracking
- End-to-end encryption
- Resume broken downloads
- Bandwidth limiting
- Advanced UI with progress bars
- User authentication
- Search functionality
- NAT traversal

## License

Open source - Educational purposes

## Credits

Comprehensive P2P file-sharing system demonstrating core distributed systems concepts.

---

**Ready to share files P2P! 🚀**
