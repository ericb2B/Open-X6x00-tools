"""Configuration and constants for TCI Audio Interface."""

import os

# Default server configuration
DEFAULT_SERVER_IP = "192.168.1.200"
DEFAULT_SERVER_PORT = "50001"

# Audio configuration
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_DTYPE = "float32"
AUDIO_BLOCKSIZE = 0  # Use system default

# Virtual device names
VIRTUAL_SINK_NAME = "tci_rx"
VIRTUAL_SOURCE_NAME = "tci_micro"

# Directory setup
DIR_PATH = os.path.expanduser("~/tci-audio")
PYTHON_PATH = os.path.join(DIR_PATH, "venv/bin/python")

# Queue configuration
AUDIO_QUEUE_MAXSIZE = 10

# S-meter thresholds
S9_THRESHOLD = 50
S9_PLUS_THRESHOLD = 40

# UI Configuration
WINDOW_TITLE = "TCI Audio Interface"
WINDOW_SIZE = "640x580"
WINDOW_RESIZABLE = False