import os
import tempfile
import openai
from database import get_session_interactions
from dotenv import load_dotenv
from rag import initialize_rag

load_dotenv()


class AssistantResponder:
    """Generates responses using OpenAI and provides TTS capabilities"""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        openai.api_key = os.getenv("OPENAI_API_KEY")

        db_path = os.path.join(os.path.dirname(__file__), 'speech_app.db')
        self.rag = initialize_rag(db_path)
        print(f"RAG initialized: {self.rag is not None}")

        # TTS engine settings
        self.tts_engine = "pyttsx3"  # Default engine

        # Initialize pyttsx3
        try:
            import pyttsx3
            self.pyttsx3_engine = pyttsx3.init()
            print("pyttsx3 initialized")
        except Exception as e:
            self.pyttsx3_engine = None
            print(f"pyttsx3 initialization failed: {e}")

        # Kokoro TTS setup
        self.kokoro_pipeline = None
        self.kokoro_loaded = False
        self.kokoro_voice = os.getenv("KOKORO_VOICE", "af_heart")
        self.kokoro_speed = float(os.getenv("KOKORO_SPEED", "1.1"))
        self.device = self._detect_device()

    def _detect_device(self):
        """Detect if CUDA is available for Kokoro"""
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_kokoro(self):
        """Load the Kokoro TTS engine"""
        if self.kokoro_loaded:
            return True

        try:
            from kokoro import KPipeline
            self.kokoro_pipeline = KPipeline(lang_code='a', device=self.device)
            self.kokoro_loaded = True
            return True
        except ImportError:
            print("To use Kokoro TTS: pip install kokoro torch soundfile")
            return False
        except Exception as e:
            print(f"Error loading Kokoro: {e}")
            return False

    def set_tts_engine(self, engine_name):
        """Switch TTS engine"""
        if engine_name not in ["pyttsx3", "kokoro"]:
            return {"success": False, "message": "Invalid TTS engine name"}

        old_engine = self.tts_engine
        self.tts_engine = engine_name

        # Load kokoro if needed
        if engine_name == "kokoro" and not self.kokoro_loaded:
            if not self._load_kokoro():
                self.tts_engine = "pyttsx3"
                return {
                    "success": False,
                    "message": "Failed to load Kokoro. Using pyttsx3 instead.",
                    "engine": "pyttsx3"
                }

        return {
            "success": True,
            "message": f"Switched from {old_engine} to {self.tts_engine}",
            "engine": self.tts_engine
        }

    def get_tts_engine(self):
        """Get the current TTS engine name"""
        return self.tts_engine

    def get_response(self, session_id: int) -> str:
        """Generate a response using conversation history AND memory retrieval"""
        db_session = self.session_factory()
        try:
            # Get current session interactions
            interactions = get_session_interactions(self.session_factory, session_id)

            # Create messages with system prompt and conversation history
            messages = [
                {"role": "system",
                 "content": "You are a helpful AI assistant that specializes in helping users plan events. Respond concisely and helpfully."}
            ]

            # Find latest user message for RAG query
            latest_user_message = None
            for interaction in sorted(interactions, key=lambda x: x.timestamp, reverse=True):
                if interaction.role == "user":
                    latest_user_message = interaction.transcript
                    break

            # Add conversation history from current session
            for interaction in sorted(interactions, key=lambda x: x.timestamp):
                messages.append({"role": interaction.role, "content": interaction.transcript})

            # MEMORY FEATURE: Retrieve relevant past interactions using RAG
            relevant_memories = ""
            if self.rag and latest_user_message:
                try:
                    print(f"Retrieving memories for: {latest_user_message[:50]}...")
                    relevant_memories = self.rag.get_relevant_memories_for_prompt(
                        latest_user_message,
                        limit=3,
                        prefix="Here are some relevant memories from previous conversations:"
                    )
                    print(f"Retrieved memories: {relevant_memories[:100]}...")
                except Exception as e:
                    print(f"Error retrieving memories: {e}")

            # Add memory context to system message if available
            if relevant_memories:
                system_message = (
                    "You are a helpful AI assistant that specializes in helping users plan events. "
                    "You have access to memories from previous conversations with this user. "
                    "Use these memories to provide more personalized assistance. "
                    f"\n\n{relevant_memories}\n\n"
                    "Respond concisely and helpfully using this context when relevant."
                )
                messages[0]["content"] = system_message

            # Generate response
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )

            # MEMORY FEATURE: Store embeddings for future retrieval
            if self.rag and latest_user_message:
                for interaction in sorted(interactions, key=lambda x: x.timestamp, reverse=True):
                    if interaction.role == "user":
                        try:
                            success = self.rag.store_interaction_embedding(
                                session_id=session_id,
                                interaction_id=interaction.id,
                                transcript=interaction.transcript
                            )
                            print(f"Stored embedding for interaction {interaction.id}: {success}")
                        except Exception as e:
                            print(f"Error storing interaction embedding: {e}")
                        break

            return response.choices[0].message.content

        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm sorry, but I ran into an error. Could you please try again?"
        finally:
            db_session.close()

    def speak_response(self, text: str, socketio):
        """Generate TTS audio and stream via SocketIO"""
        if not text:
            return

        try:
            # Create temp file for audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name

            # Use Kokoro if selected and available
            if self.tts_engine == "kokoro" and (self.kokoro_loaded or self._load_kokoro()):
                import soundfile as sf
                generator = self.kokoro_pipeline(text, voice=self.kokoro_voice, speed=self.kokoro_speed)

                # Get the first audio chunk
                for i, (gs, ps, audio) in enumerate(generator):
                    if i == 0:
                        sf.write(temp_filename, audio, 24000)
                        break

            # Use pyttsx3 as fallback
            elif self.pyttsx3_engine:
                self.pyttsx3_engine.save_to_file(text, temp_filename)
                self.pyttsx3_engine.runAndWait()
            else:
                print("No TTS engine available")
                return

            # Read and emit the audio data
            with open(temp_filename, "rb") as f:
                socketio.emit("tts_audio", f.read())

            # Clean up
            os.remove(temp_filename)

        except Exception as e:
            print(f"Error in text-to-speech: {e}")