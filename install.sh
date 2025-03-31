#!/bin/bash

# Check if virtual environment exists, create it if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install required packages from requirements.txt
echo "Installing required packages..."
pip install -r requirements.txt

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: FFmpeg is not installed, which is required for audio processing."
    echo "Please install FFmpeg:"
    echo "  - On macOS: brew install ffmpeg"
    echo "  - On Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  - On Windows: Download from https://ffmpeg.org/download.html"
fi

echo ""
echo "Installation complete! To run the application:"
echo "1. Make sure your virtual environment is activated: source .venv/bin/activate"
echo "2. Run the application: python app.py"
echo "3. Open your browser to http://localhost:5050" 