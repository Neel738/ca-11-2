# Speech Recognition Web App

A real-time speech recognition application using Flask, WebSockets, and OpenAI's Whisper for transcription.

## Features

- Real-time audio streaming from browser to server
- Speech-to-text transcription using OpenAI's Whisper model
- Automatic pause detection
- Visual feedback for recording and processing states
- Chat-like interface for displaying transcriptions

## Requirements

- Python 3.7+
- Flask
- Flask-SocketIO
- OpenAI Whisper
- FFmpeg (system dependency)
- NumPy
- SoundFile

## Quick Setup

The easiest way to get started is to use the included setup script:

```bash
# Make the script executable if needed
chmod +x setup.sh

# Run the setup script
./setup.sh
```

This script will:
1. Create a virtual environment (if it doesn't exist)
2. Activate the virtual environment
3. Install all required Python packages
4. Check if FFmpeg is installed

## Manual Installation

If you prefer to set up manually:

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install Python dependencies:
   ```bash
   pip install flask flask-socketio openai-whisper numpy soundfile
   ```

3. Install FFmpeg (if not already installed):
   - On macOS: `brew install ffmpeg`
   - On Ubuntu/Debian: `sudo apt install ffmpeg`
   - On Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)

## Running the Application

Once setup is complete:

1. Make sure your virtual environment is activated:
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Start the Flask application:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

4. Click the microphone button to start recording. The application will automatically detect pauses in speech and transcribe the audio.

## Troubleshooting

### Microphone Issues
- Make sure you've granted microphone permissions in your browser
- Check if your microphone is working in other applications
- Try using headphones to reduce echo

### Transcription Issues
- If transcriptions are empty or errors occur, try speaking louder or in a clearer environment
- The app works best with clear, concise speech
- Short phrases (5-10 seconds) work better than long monologues

### Connection Issues
- Make sure the Flask server is running
- Check if you can access the app at http://localhost:5000
- If you get "WebSocket connection failed" errors, try restarting the Flask server

### Package Installation Issues
- If you have issues installing packages, make sure your Python version is 3.7 or higher
- Try upgrading pip: `pip install --upgrade pip`
- Make sure FFmpeg is correctly installed and accessible in your PATH

## Usage

1. Click the "Start Listening" button to begin recording
2. Speak into your microphone
3. When you pause, the app will detect the silence and process the audio
4. The transcribed text will appear in the chat interface
5. The microphone will automatically re-enable for the next recording

## Notes

- The application uses WebSockets for real-time communication
- Audio processing is done on the server using OpenAI's Whisper
- The silence detection threshold can be adjusted in the server code
- The application requires microphone permissions in the browser 