import os
import openai
from database import get_session_interactions
from dotenv import load_dotenv
from flask_socketio import emit
load_dotenv()


class AssistantResponder:
    """
    A class that uses OpenAI to generate responses and also provides
    text-to-speech capabilities for speaking the generated response.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = api_key
        
        # Initialize TTS engine (optional)
        self.engine = None
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            print("Text-to-speech engine initialized successfully")
        except Exception as e:
            print(f"Text-to-speech engine initialization failed: {e}")
            print("Running without text-to-speech support")

    def get_response(self, session_id: int) -> str:
        
        """
        Generate a response from OpenAI using all previous user and assistant
        messages in the current session as the conversation context.
        """
        db_session = self.session_factory()
        try:
            print(f"Starting to generate response for session ID: {session_id}")
            # 1) Get all interactions for the session
            interactions = get_session_interactions(self.session_factory, session_id)

            # 2) Build a conversation context list of messages
            #    We add a system prompt at the beginning to set the tone or instructions of the assistant
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant that specializes in helping users plan events. "
                        "You have access to the conversation so far. Respond in a concise, polite, and helpful way."
                    )
                }
            ]

            # Sort interactions by timestamp (just in case they aren't sorted).
            interactions_sorted = sorted(interactions, key=lambda x: x.timestamp)

            # Convert each interaction to the appropriate role/content for the chat
            for interaction in interactions_sorted:
                if interaction.role == "assistant":
                    messages.append({"role": "assistant", "content": interaction.transcript})
                else:
                    # We'll treat "user" as a normal user message
                    messages.append({"role": "user", "content": interaction.transcript})

            # 3) Call the OpenAI Chat Completion endpoint
            print("Calling OpenAI API to generate response...")
            # This is intentionally a blocking call - we want to show the thinking status while we wait
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=200,
                temperature=0.7)
            
            # 4) Extract the assistant's text from the response
            assistant_text = response.choices[0].message.content
            print("Response generated successfully")

            return assistant_text

        except Exception as e:
            print(f"Error in generate_openai_response: {e}")
            return "I'm sorry, but I ran into an error. Could you please try again?"
        finally:
            db_session.close()


    def speak_response(self, text: str):
        """
        Convert the given text to speech using pyttsx3.
        """
        if not text or not self.engine:
            return  # Don't speak empty text or if engine not available
        
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
