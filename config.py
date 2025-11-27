"""
Configuration file for P2P File-Sharing System

Copy this file and customize as needed.
"""

# ============================================================================
# TRACKER SERVER CONFIGURATION
# ============================================================================

# Tracker server listening address
TRACKER_HOST = '127.0.0.1'

# Tracker server listening port
TRACKER_PORT = 5000

# Server socket buffer size
TRACKER_BUFFER_SIZE = 4096

# Maximum pending connections
TRACKER_MAX_CONNECTIONS = 5


# ============================================================================
# PEER CLIENT CONFIGURATION
# ============================================================================

# Tracker server address (where to connect to)
TRACKER_HOST_CLIENT = '127.0.0.1'
TRACKER_PORT_CLIENT = 5000

# Peer server port (listen for chunk requests from other peers)
PEER_PORT = 6000

# Socket buffer size for peer-to-peer communication
PEER_BUFFER_SIZE = 4096

# Maximum connections peer server can accept
PEER_MAX_CONNECTIONS = 5


# ============================================================================
# FILE TRANSFER CONFIGURATION
# ============================================================================

# Default chunk size in bytes (256 KB)
CHUNK_SIZE = 262144

# Minimum chunk size (64 KB)
MIN_CHUNK_SIZE = 65536

# Maximum chunk size (1 MB)
MAX_CHUNK_SIZE = 1048576

# Timeout for chunk download in seconds
DOWNLOAD_TIMEOUT = 10.0

# Timeout for tracker communication in seconds
TRACKER_TIMEOUT = 5.0


# ============================================================================
# DIRECTORY CONFIGURATION
# ============================================================================

# Directory for shared files and chunks
SHARED_DIRECTORY = "shared"

# Subdirectory for chunks
CHUNKS_SUBDIRECTORY = "chunks"

# Directory for downloaded files
DOWNLOADS_DIRECTORY = "downloads"


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# Log format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Log to file (optional)
LOG_FILE = None  # Set to 'app.log' to enable file logging


# ============================================================================
# PERFORMANCE CONFIGURATION
# ============================================================================

# Number of threads for handling peer connections
NUM_HANDLER_THREADS = 5

# Enable socket keepalive
ENABLE_KEEPALIVE = True

# Socket keepalive timeout in seconds
KEEPALIVE_TIMEOUT = 3600

# Connection reuse address (SO_REUSEADDR)
ENABLE_REUSE_ADDR = True


# ============================================================================
# ADVANCED FEATURES
# ============================================================================

# Enable automatic peer discovery (future feature)
ENABLE_DISCOVERY = False

# Enable bandwidth limiting (future feature)
ENABLE_BANDWIDTH_LIMIT = False
BANDWIDTH_LIMIT_KBPS = 1000  # Kilobytes per second

# Enable encryption (future feature)
ENABLE_ENCRYPTION = False

# Enable compression (future feature)
ENABLE_COMPRESSION = False

# Maximum file size (0 = unlimited)
MAX_FILE_SIZE = 0  # bytes

# Maximum number of concurrent downloads per peer
MAX_CONCURRENT_DOWNLOADS = 5
