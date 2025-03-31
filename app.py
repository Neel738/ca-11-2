from flask import Flask, render_template, request, redirect, url_for, session as flask_session
from flask_socketio import SocketIO, emit
import os
from speechrecognition import SpeechRecognizer
from database import init_db, create_session, store_interaction, get_session_interactions, store_entities, get_all_sessions, get_session_entities
from entity_extraction import EntityExtractor
from assistant_responses import AssistantResponder

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'speech-recognition-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Database
db_path = os.path.join(os.path.dirname(__file__), 'speech_app.db')
Session = init_db(db_path)

# Initialize components
speech_recognizer = SpeechRecognizer()
entity_extractor = EntityExtractor()
assistant_responder = AssistantResponder(Session)

# Active session
current_session_id = None

@app.route('/')
def index():
    """Render the main application page"""
    global current_session_id
    
    # Check if we need to create a new session
    if 'session_id' not in flask_session or not current_session_id:
        db_session = create_session(Session)
        current_session_id = db_session.id
        flask_session['session_id'] = current_session_id
        print(f"Created new session with ID: {current_session_id}")
    else:
        current_session_id = flask_session['session_id']
        print(f"Using existing session with ID: {current_session_id}")
    
    return render_template('index.html', session_id=current_session_id)

@app.route('/end_session')
def end_session():
    """End the current session and start a new one"""
    global current_session_id
    
    # Create a new session
    db_session = create_session(Session)
    current_session_id = db_session.id
    flask_session['session_id'] = current_session_id
    print(f"Started new session with ID: {current_session_id}")
    
    return redirect(url_for('index'))

@app.route('/information', methods=['GET', 'POST'])
def information():
    """Show database information (password protected)"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '1234':
            # Get all sessions with their interactions and entities
            all_sessions = get_all_sessions(Session)
            sessions_data = []
            
            for session in all_sessions:
                interactions = get_session_interactions(Session, session.id)
                session_entities = get_session_entities(Session, session.id)
                
                # Format the data
                formatted_interactions = []
                for interaction in interactions:
                    interaction_entities = [e for e in session_entities if e.interaction_id == interaction.id]
                    formatted_entities = [{"type": e.entity_type, "value": e.entity_value} for e in interaction_entities]
                    
                    formatted_interactions.append({
                        "id": interaction.id,
                        "timestamp": interaction.timestamp,
                        "role": interaction.role,
                        "transcript": interaction.transcript,
                        "entities": formatted_entities
                    })
                
                sessions_data.append({
                    "id": session.id,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "interactions": formatted_interactions
                })
            
            return render_template('information.html', sessions=sessions_data, authenticated=True)
        else:
            return render_template('information.html', error="Invalid password", authenticated=False)
    
    return render_template('information.html', authenticated=False)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('audio_data')
def handle_audio_data(data):
    """Process incoming audio data"""
    global current_session_id
    
    # Add audio chunk to buffer and check status
    status = speech_recognizer.add_audio_chunk(data)
    
    # If status changed, inform client
    if status:
        emit('status', {'status': status})
        
        # If we should start processing, do it
        if status == "processing":
            process_audio_workflow()

def process_audio_workflow():
    """Complete workflow for processing audio and generating response"""
    global current_session_id
    
    # Process the audio buffer to get transcription with streaming
    print("Starting transcription workflow")
    # First emit a status update to show we're starting transcription
    emit('status', {'status': 'transcribing'})
    
    transcription = speech_recognizer.transcribe_with_stream(socketio)
    
    if not transcription:
        # No transcription, reset status and return
        emit('status', {'status': 'ready'})
        return
    
    # We've already emitted the preliminary transcription from the streaming method
    # Now we mark it as final
    emit('transcription', {'text': transcription, 'final': True})
    
    # Signal that we are now processing the transcription
    emit('status', {'status': 'processing'})
    
    try:
        # 1. Store the transcription in the database
        interaction = store_interaction(
            Session,
            current_session_id,
            transcription
        )
        
        # Send debug info
        emit('debug', {
            'event': 'stored_interaction',
            'id': interaction.id,
            'session_id': current_session_id,
            'text': transcription
        })
        
        # 2. Extract entities
        entities = entity_extractor.extract_entities(transcription)
        
        # Send debug info about entities
        emit('debug', {
            'event': 'extracted_entities',
            'entities': entities
        })
        
        # 3. Store entities in the database if any were found
        if entities:
            stored_entities = store_entities(Session, interaction.id, entities)
            print(f"Stored {len(stored_entities)} entities")
            
            # Send debug info
            emit('debug', {
                'event': 'stored_entities',
                'count': len(stored_entities)
            })
        
        # Signal that we are now thinking/processing the response
        print("Emitting thinking status and thinking_start event")
        emit('status', {'status': 'thinking'})
        emit('thinking', {'status': 'started'})
        
        # 4. Signal we're generating the assistant response
        emit('debug', {
            'event': 'generating_response',
            'session_id': current_session_id
        })
        
        assistant_text = assistant_responder.get_response(current_session_id)
        
        # Signal end of thinking
        print("Emitting thinking_end event")
        emit('thinking', {'status': 'ended'})
        
        # 5. Store the assistant's response
        assistant_interaction = store_interaction(
            Session,
            current_session_id,
            assistant_text,
            role="assistant"
        )
        
        # Send debug info
        emit('debug', {
            'event': 'stored_assistant_response',
            'id': assistant_interaction.id,
            'text': assistant_text
        })
        
        # 6. Send the response to the client
        emit('assistant_response', {'text': assistant_text})
        
    except Exception as e:
        print(f"Error in process_audio_workflow: {str(e)}")
        emit('error', {'message': 'Processing failed'})
        emit('debug', {
            'event': 'error',
            'message': str(e)
        })
        
        # End thinking state on error
        print("Emitting thinking_end event due to error")
        emit('thinking', {'status': 'ended'})
    
    # Re-enable microphone
    emit('status', {'status': 'ready'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5050) 