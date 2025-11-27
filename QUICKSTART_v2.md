# Quick Start - P2P File-Sharing Client v2.0

## 🚀 Getting Started in 5 Minutes

### Step 1: Start the System (Terminal 1)

**Start Tracker Server:**
```bash
# Windows:
python tracker/tracker_server.py

# macOS/Linux:
python3 tracker/tracker_server.py
```

Expected output:
```
2024-11-27 14:23:15,123 - INFO - Tracker Server started on 127.0.0.1:5000
```

### Step 2: Start Peer Clients (Terminal 2+)

**Start Peer 1:**
```bash
# Windows:
python peer/peer_client.py

# macOS/Linux:
python3 peer/peer_client.py
```

**Start Peer 2 (new terminal):**
```bash
# Repeat the same command in a new terminal
python peer/peer_client.py
```

---

## 🎯 Test New Features

### Feature 1: Share a File

**On Peer 1:**

1. Go to **Share Files** tab
2. Click **"📁 Browse File"**
3. Select any file (e.g., document.txt, image.jpg)
4. Click **"📤 Share File"**
5. Wait for confirmation message
6. **Copy the File ID** displayed
7. File appears in "Shared Files" list ✓

**Example File ID:**
```
a1b2c3d4e5f6g7h8
```

### Feature 2: Search for File

**On Peer 2:**

1. Go to **Download Files** tab
2. Paste File ID in "File ID" field
3. Click **"🔍 Search"** button
4. View results:
   ```
   ✓ File Found!
   
   Filename: document.txt
   Chunks: 4
   Available Peers: 1
   
   Peers Seeding:
   1. 127.0.0.1:6000
   ```

✓ Search works!

### Feature 3: Download File

**On Peer 2:**

1. Keep the File ID from search
2. Click **"⬇️ Download File"** button
3. Monitor status log for progress
4. Wait for "Download complete!" message
5. File appears in **Download History** ✓

**History Entry:**
```
Filename: document.txt
Date: 2024-11-27 14:23:45
Size: 1.2 KB
Status: Completed (green)
```

### Feature 4: Filter Download History

**On Peer 2:**

1. Stay on **Download Files** tab
2. Scroll to "Download History"
3. In search box, type: `txt`
4. See only `.txt` files filtered ✓
5. Clear search → see all files
6. Try other searches: `pdf`, `2024`, `document`

---

## 🔍 Explore All Tabs

### Dashboard Tab
- View **Upload Speed** (green)
- View **Download Speed** (blue)
- See **Active Transfers** live
- Watch speeds update every second

### Share Files Tab
- **Browse and share** files
- View **Shared Files List** (auto-updates)
- Monitor **File IDs** and **Chunks**

### Download Files Tab
- **Search** for files by ID
- View **Search Results** with peer list
- See **Download History**
- **Filter history** by filename
- Download status shown as **Completed** (green) or **Failed** (red)

### Statistics Tab
- Real-time **speed display**
- **Detailed transfer log**
- See all **UPLOAD** (green) and **DOWNLOAD** (blue) operations
- Track **chunk numbers** and **peer addresses**

### Settings Tab
- **Configure tracker** (host/port)
- View **Status Log** with timestamps
- **Clear Log** button
- **Open Downloads** folder
- **Open Shared** folder

---

## 📊 Multi-Window Testing

### Test Setup
```
Terminal 1: Tracker Server (stays running)
Terminal 2: Peer Client 1 (Seeder)
Terminal 3: Peer Client 2 (Downloader)
```

### Complete Workflow
1. **Tracker**: Running on port 5000
2. **Peer 1**: Shares file (seeder)
3. **Peer 2**: Searches → Downloads → Verifies in history
4. **Monitor**: Both dashboards show activity

### Expected Results
```
Peer 1 Dashboard:
- Upload Speed: 50+ KB/s
- Active Transfers: Shows downloads to Peer 2
- Shared Files: File listed

Peer 2 Dashboard:
- Download Speed: 50+ KB/s
- Active Transfers: Shows uploads from Peer 1
- Download History: File recorded as "Completed"
```

---

## 🎨 UI Feature Verification

### Check These on Each Tab

#### Dashboard ✓
- [ ] Peer ID displays
- [ ] Port shows correct number
- [ ] Upload speed updates (green)
- [ ] Download speed updates (blue)
- [ ] Transfers table shows activity
- [ ] Table updates every second

#### Share Files ✓
- [ ] Can browse files
- [ ] Filename displays after selection
- [ ] Can click "Share File"
- [ ] Confirmation message appears
- [ ] File appears in shared list
- [ ] File ID shown (8 chars)
- [ ] Chunk count shows

#### Download Files ✓
- [ ] Can enter File ID
- [ ] Search returns results
- [ ] Results show file details
- [ ] Peers list displays
- [ ] Can download file
- [ ] History records download
- [ ] Search filter works real-time
- [ ] Filter is case-insensitive
- [ ] Status shows Completed/Failed

#### Statistics ✓
- [ ] Speed display updates
- [ ] Transfer log shows activity
- [ ] Uploads colored green
- [ ] Downloads colored blue
- [ ] Timestamps display
- [ ] Peer addresses shown
- [ ] Chunk numbers shown
- [ ] Bytes transferred shown

#### Settings ✓
- [ ] Tracker host field editable
- [ ] Tracker port field editable
- [ ] Status log shows messages
- [ ] Messages have timestamps
- [ ] Clear log button works
- [ ] Open Downloads button works
- [ ] Open Shared button works

---

## 🐛 Troubleshooting

### Search Returns "File not found"
**Solutions:**
1. Check File ID is copied correctly (case-sensitive)
2. Verify Peer 1 is sharing the file
3. Check Peer 1's "Shared Files" shows file
4. Verify tracker is running (port 5000)

### Download Fails
**Solutions:**
1. Check Peer 1 is still running
2. Check download folder has write permissions
3. Try smaller file first
4. Check status log for errors
5. Restart peers

### Filter Not Working
**Solutions:**
1. Make sure you have downloads first
2. Type search term slowly
3. Clear search box first
4. Check spelling
5. Remember: search is case-insensitive

### Speeds Not Updating
**Solutions:**
1. Perform actual transfers (share/download)
2. Monitor dashboard during transfer
3. Check status log for activity
4. Verify network connection

### Folder Buttons Don't Work
**Solutions:**
1. Check folders exist (created automatically)
2. On Windows, may need to be in foreground
3. Try using file explorer directly
4. Check file permissions

---

## 📈 Performance Tips

### Speed Up Downloads
- [ ] Use peer with good connectivity
- [ ] Download fewer chunks simultaneously
- [ ] Close other applications
- [ ] Check network bandwidth

### Monitor Seeding
- [ ] Keep peer client running
- [ ] Watch upload speed in dashboard
- [ ] Check active transfers
- [ ] Monitor statistics tab

### Optimize System
- [ ] Don't share too many files
- [ ] Limit concurrent downloads
- [ ] Monitor RAM usage
- [ ] Keep chunks folder organized

---

## 📚 Documentation Files

After testing, read these for detailed info:

| File | Purpose |
|------|---------|
| `UI_ADVANCED_GUIDE.md` | Complete feature guide |
| `UI_LAYOUT_VISUAL.md` | Visual layout reference |
| `FEATURES_NEW_v2.0.md` | New features summary |
| `SETUP.md` | Installation guide |
| `README_FULL.md` | Full documentation |

---

## ✅ Verification Checklist

After testing all features:

- [ ] All 5 tabs accessible
- [ ] File sharing works
- [ ] File search returns results
- [ ] Downloads complete successfully
- [ ] Download history records files
- [ ] History filter works
- [ ] Shared files list displays
- [ ] Statistics update in real-time
- [ ] Speed display shows correct values
- [ ] Settings configurable
- [ ] Folder access works
- [ ] Status log shows messages
- [ ] No error messages
- [ ] UI responsive and smooth
- [ ] All colors display correctly

---

## 🎓 Next Steps

After basic testing:

1. **Share multiple files** - Test with different file types
2. **Download multiple times** - Build history
3. **Test filtering** - Try various search terms
4. **Monitor statistics** - Analyze performance
5. **Read full docs** - Understand all features
6. **Stress test** - Try with large files
7. **Multi-peer test** - Use 3+ peers simultaneously

---

## 🚀 You're Ready!

The enhanced P2P File-Sharing Client v2.0 is ready to use!

### Key Improvements You'll See:
✓ Beautiful multi-tab interface
✓ Powerful search functionality
✓ Download history with filtering
✓ Real-time monitoring
✓ Professional design

### Enjoy!
```
╔════════════════════════════════════════╗
║  P2P File-Sharing Client v2.0          ║
║                                        ║
║  ✓ Search for files by name            ║
║  ✓ Download with peer tracking         ║
║  ✓ Monitor speeds in real-time         ║
║  ✓ Filter download history             ║
║  ✓ Professional multi-tab UI           ║
║                                        ║
║  Ready to use! Start sharing now!      ║
╚════════════════════════════════════════╝
```

---

**Version**: 2.0
**Last Updated**: November 27, 2024
**Status**: Production Ready ✅
