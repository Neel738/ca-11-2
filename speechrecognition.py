import numpy as np
import whisper
import time
import tempfile
import soundfile as sf
import os
from flask_socketio import emit


class SpeechRecognizer:
    """Speech recognition handler using OpenAI's Whisper model"""

    def __init__(self, model_name="tiny"):
        """Initialize the speech recognizer with the specified model"""
        print(f"Loading Whisper model: {model_name}")
        self.model = whisper.load_model(model_name)

        # Settings for speech detection
        self.audio_buffer = []
        self.is_speaking = False
        self.last_audio_time = 0
        self.SILENCE_THRESHOLD = 1.0  # seconds of silence before processing
        self.ENERGY_THRESHOLD = 0.005  # lower threshold for speech detection
        self.streaming = False  # Flag for streaming mode

    def add_audio_chunk(self, data):
        """Add an audio chunk to the buffer and detect speech/silence"""
        try:
            audio_chunk = np.frombuffer(data, dtype=np.float32)

            # Skip if chunk is too small or empty
            if len(audio_chunk) < 10:
                return None

            self.audio_buffer.append(audio_chunk)

            # Check if audio contains speech or silence
            energy = np.mean(np.abs(audio_chunk))
            current_time = time.time()

            if energy > self.ENERGY_THRESHOLD:
                self.is_speaking = True
                self.last_audio_time = current_time
                return "listening"
            elif self.is_speaking and (current_time - self.last_audio_time) > self.SILENCE_THRESHOLD:
                # Silence detected after speech
                self.is_speaking = False
                return "processing"

            return None
        except Exception as e:
            print(f"Error processing audio chunk: {str(e)}")
            return None

    def process_audio(self):
        """Process the complete audio buffer and transcribe using Whisper"""
        if not self.audio_buffer or len(self.audio_buffer) < 3:  # Need at least some chunks to process
            print("Audio buffer too small, skipping transcription")
            return None

        try:
            # Combine audio chunks
            audio_data = np.concatenate(self.audio_buffer)

            # Validate audio data
            if len(audio_data) < 1000:  # Audio too short to process
                print("Audio too short to transcribe")
                self.audio_buffer = []  # Clear buffer for next recording
                return None

            # Clear buffer for next recording
            self.audio_buffer = []

            # Save as temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name
                sf.write(temp_filename, audio_data, 16000)

            # Transcribe with Whisper
            result = self.model.transcribe(temp_filename, fp16=False)
            transcription = result["text"].strip()

            print(f"Transcription: {transcription}")

            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

            return transcription if transcription else None

        except Exception as e:
            print(f"Error during transcription: {str(e)}")
            # Clear buffer on error
            self.audio_buffer = []
            return None

    def transcribe_with_stream(self, socketio):
        """Process the audio buffer and stream the transcription using Whisper"""
        if not self.audio_buffer or len(self.audio_buffer) < 3:
            print("Audio buffer too small, skipping transcription")
            return None

        try:
            print("Starting transcription process...")
            # Combine audio chunks
            audio_data = np.concatenate(self.audio_buffer)

            # Validate audio data
            if len(audio_data) < 1000:  # Audio too short to process
                print("Audio too short to transcribe")
                self.audio_buffer = []  # Clear buffer for next recording
                return None

            # Save as temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name
                sf.write(temp_filename, audio_data, 16000)

            # We don't emit status here - app.py handles the status flow

            # Transcribe with Whisper (using regular transcribe for now, as streaming isn't directly supported)
            print("Calling Whisper model to transcribe...")
            result = self.model.transcribe(
                temp_filename,
                fp16=False,
                # We can't actually stream with the standard Whisper API, but we get the transcription quickly
                # In a production app, you'd want to use a real streaming implementation
            )

            transcription = result["text"].strip()

            # Emit the transcription immediately, before processing
            if transcription:
                print(f"Emitting preliminary transcription: {transcription}")
                socketio.emit('transcription', {'text': transcription, 'final': False})
                # Don't emit status here - let app.py handle the status flow

            print(f"Transcription (streamed): {transcription}")

            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

            # Reset buffer for next recording
            self.audio_buffer = []

            return transcription if transcription else None

        except Exception as e:
            print(f"Error during streaming transcription: {str(e)}")
            # Clear buffer on error
            self.audio_buffer = []
            return None