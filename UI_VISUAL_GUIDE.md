# Enhanced UI Visual Guide

## Window Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ P2P File-Sharing Client - Enhanced                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─ Peer Information & Speed ────────────────────────────────────────────┐  │
│  │ Peer ID: a1b2c3d4                      Upload Speed: 1250.50 KB/s   │  │
│  │ Server Port: 6000                      Download Speed: 850.25 KB/s  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Tracker Configuration ──────────────────────────────────────────────┐  │
│  │ Host: [127.0.0.1___]    Port: [5000_]                               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Share File ─────────────────────────────────────────────────────────┐  │
│  │ my_video.mp4                                                         │  │
│  │ [Select File]  [Share]                                              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Download File ──────────────────────────────────────────────────────┐  │
│  │ File ID: [abc123def456____________________]  [Download]              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌─ Active Transfers ──────────────────────────────────────────────────┐   │
│  │ Type     │ Peer              │ File ID  │ Chunk │ Bytes   │ Time     │ ↑ │
│  ├──────────┼───────────────────┼──────────┼───────┼─────────┼──────────┤ │ │
│  │ UPLOAD   │ 192.168.1.100:50  │ abc123   │ 5     │ 256 KB  │ 14:30:45 │ │ │
│  │ UPLOAD   │ 192.168.1.101:51  │ def456   │ 8     │ 256 KB  │ 14:30:44 │ │ │
│  │ DOWNLOAD │ 192.168.1.50:6000 │ abc123   │ 0     │ 256 KB  │ 14:30:42 │ │ │
│  │ DOWNLOAD │ 192.168.1.51:6000 │ abc123   │ 1     │ 256 KB  │ 14:30:41 │ ↓ │
│  └──────────┴───────────────────┴──────────┴───────┴─────────┴──────────┘   │
│                                                                               │
│  ┌─ Status Log ─────────────────────────────────────────────────────────┐  │
│  │ [14:30:45] Peer ID: a1b2c3d4                                        │  │
│  │ [14:30:46] Peer Server running on port 6000                         │  │
│  │ [14:30:47] Starting file sharing process...                         │  │
│  │ [14:30:48] File ID: abc123def456                                    │  │
│  │ [14:30:49] Splitting file into chunks (size: 262144 bytes)...       │  │
│  │ [14:30:50] Created 40 chunks                                        │  │
│  │ [14:30:51] Registering with tracker...                              │  │
│  │ [14:30:52] Successfully shared file! File ID: abc123def456          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  [Clear Log]  [Refresh Stats]                                              │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Color Coding

### Upload Transfers (Seeding)
- **Color**: Green
- **Meaning**: You are uploading chunks to another peer
- **Speed Display**: Green text in top-right

### Download Transfers
- **Color**: Blue
- **Meaning**: You are downloading chunks from another peer
- **Speed Display**: Blue text in top-right

### Log Messages
- **Format**: `[HH:MM:SS] Message text`
- **Scroll**: Auto-scrolls to show latest messages

## Speed Meters Explanation

### Upload Speed (Seeding)
```
Upload Speed: 1250.50 KB/s
    ↑
    └─ Real-time upload speed to other peers
       Updates every second
```

**What it means:**
- File chunks are being uploaded at this rate
- Higher = More peers requesting your files
- Indicates your seeding contribution

### Download Speed
```
Download Speed: 850.25 KB/s
    ↑
    └─ Real-time download speed from peers
       Updates every second
```

**What it means:**
- File chunks are being downloaded at this rate
- Higher = Better network connection to peers
- Indicates download performance

## Active Transfers Table

### Column Explanations

**Type Column**
```
UPLOAD   = You are sending chunks to a peer (seeding)
DOWNLOAD = You are receiving chunks from a peer
```

**Peer Column**
```
192.168.1.100:50123 = Peer IP address and port
├── 192.168.1.100 = Peer's IP
└── 50123 = Peer's port number
```

**File ID Column**
```
abc123 = First 8 characters of the full file ID
       (Shortened for readability, full ID is 16 chars)
```

**Chunk Column**
```
5 = Chunk index being transferred (0-indexed)
   Chunk 0 = First 256 KB
   Chunk 1 = Next 256 KB
   ...
```

**Bytes Column**
```
256 KB = Size of the chunk transferred
         (Showing KB for readability)
```

**Time Column**
```
14:30:45 = Timestamp when transfer occurred (HH:MM:SS)
           Shows the exact moment
```

## Real-Time Updates

### Every 1 Second:
1. **Speed values recalculate**
   - Upload speed = Total uploads / elapsed time
   - Download speed = Total downloads / elapsed time

2. **Active transfers refresh**
   - New transfers appear at top
   - Recent 20 transfers displayed
   - Color-coded by type

3. **Status log visible**
   - Shows detailed events
   - Auto-scrolls for latest entries

## Interactive Elements

### Buttons

**Select File**
- Browse your computer
- Choose file to share
- Updates "Share File" section

**Share**
- Starts file sharing process
- Splits into chunks
- Registers with tracker
- Displays File ID
- Shows in status log

**Download**
- Requires File ID
- Queries tracker for file
- Downloads from available peers
- Updates active transfers in real-time
- Shows in status log

**Clear Log**
- Removes all status log entries
- Doesn't affect stats or transfers

**Refresh Stats**
- Manually refresh active transfers display
- Useful if updates seem stuck

### Input Fields

**Tracker Host**
- Default: 127.0.0.1
- Can be changed before operations
- IP address of tracker server

**Tracker Port**
- Default: 5000
- Can be changed before operations
- Port of tracker server

**File ID**
- Enter File ID to download
- Copy from another peer's display
- 16-character hex string

## Multi-Peer Scenario

### Peer 1 (Seeding)
```
Upload Speed: 2100.75 KB/s  ← High speed, multiple downloads

Active Transfers:
Type     | Peer              | File ID  | Chunk
---------|-------------------|----------|-------
UPLOAD   | 192.168.1.100:50  | abc123   | 0
UPLOAD   | 192.168.1.100:50  | abc123   | 1
UPLOAD   | 192.168.1.101:51  | abc123   | 5
UPLOAD   | 192.168.1.102:52  | abc123   | 10
```

### Peer 2 (Downloading)
```
Download Speed: 1050.40 KB/s  ← Moderate speed, downloading

Active Transfers:
Type     | Peer              | File ID  | Chunk
---------|-------------------|----------|-------
DOWNLOAD | 192.168.1.50:6000 | abc123   | 0
DOWNLOAD | 192.168.1.50:6000 | abc123   | 1
DOWNLOAD | 192.168.1.51:6000 | abc123   | 5
```

## Performance Indicators

### Good Performance
- Upload Speed: > 500 KB/s
- Download Speed: > 500 KB/s
- Active Transfers: Multiple entries
- Log: No errors

### Moderate Performance
- Upload Speed: 100-500 KB/s
- Download Speed: 100-500 KB/s
- Active Transfers: Few entries
- Log: Normal operation

### Low Performance
- Upload Speed: < 100 KB/s
- Download Speed: < 100 KB/s
- Active Transfers: Rare entries
- Log: Check for connection issues

## Troubleshooting Visual Cues

### Speed Shows 0 KB/s
```
✗ No transfers happening
  - Check if tracker server is running
  - Verify file is shared correctly
  - Check network connectivity
```

### No Transfers in Table
```
✗ No active transfers
  - Transfers complete very quickly (may not show)
  - No downloads initiated
  - No uploads requested
  ✓ This is normal if idle
```

### Errors in Status Log
```
✗ [14:30:50] ERROR: Connection refused
  - Tracker server not running
  - Wrong IP/port configured
  - Firewall blocking
```

### Stuck on "Querying tracker..."
```
✗ Appears frozen
  - Check tracker server status
  - Verify network connectivity
  - May timeout after 5 seconds
```

---

**Visual monitoring makes P2P transfers transparent!** 👀
