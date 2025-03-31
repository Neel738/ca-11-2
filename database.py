from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Session(Base):
    """Model for storing conversation sessions."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    user_id = Column(String, nullable=True)  # Optional for GDPR compliance

    # Relationships
    interactions = relationship("Interaction", back_populates="session", cascade="all, delete-orphan")


class Interaction(Base):
    """Model for storing speech interactions."""
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    transcript = Column(String, nullable=False)
    audio_duration = Column(Float)  # Duration in seconds
    priority = Column(Boolean, default=False)  # Priority flag for important interactions

    # Relationships
    session = relationship("Session", back_populates="interactions")
    entities = relationship("Entity", back_populates="interaction", cascade="all, delete-orphan")

    role = Column(String, default="user")  # can be "user" or "assistant"


class Entity(Base):
    """Model for storing entities extracted from conversations."""
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    interaction_id = Column(Integer, ForeignKey('interactions.id'), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_value = Column(String, nullable=False)

    # Relationship to interaction
    interaction = relationship("Interaction", back_populates="entities")


def init_db(db_path: str) -> sessionmaker:
    """Initialize the database and return a session factory."""
    engine = create_engine(f"sqlite:///{db_path}", echo=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def create_session(session_factory: sessionmaker, user_id: Optional[str] = None) -> Session:
    """Create a new session."""
    db_session = session_factory()
    try:
        new_session = Session(
            start_time=datetime.utcnow(),
            user_id=user_id
        )
        db_session.add(new_session)
        db_session.commit()

        # Refresh the session to get the generated ID
        db_session.refresh(new_session)

        # Create a detached copy
        return Session(
            id=new_session.id,
            start_time=new_session.start_time,
            user_id=new_session.user_id
        )
    finally:
        db_session.close()

def end_session(session_factory: sessionmaker, session_id: int) -> None:
    """End a session by setting its end time."""
    db_session = session_factory()
    try:
        session = db_session.query(Session).filter_by(id=session_id).first()
        if session:
            session.end_time = datetime.utcnow()
            db_session.commit()
    finally:
        db_session.close()


def store_interaction(
        session_factory: sessionmaker,
        session_id: int,
        transcript: str,
        audio_duration: Optional[float] = None,
        priority: bool = False,
        role: str = "user"
) -> Interaction:
    """Store a new interaction in the database with priority flag."""
    db_session = session_factory()

    try:
        interaction = Interaction(
            session_id=session_id,
            transcript=transcript,
            audio_duration=audio_duration,
            priority=priority,
            role=role
        )
        db_session.add(interaction)
        db_session.commit()

        # Refresh to get the generated ID and timestamp
        db_session.refresh(interaction)

        # Create a detached copy with all attributes
        detached_interaction = Interaction(
            id=interaction.id,
            session_id=interaction.session_id,
            timestamp=interaction.timestamp,
            transcript=interaction.transcript,
            audio_duration=interaction.audio_duration,
            priority=interaction.priority,
            role=interaction.role
        )
        return detached_interaction
    finally:
        db_session.close()

def get_session_interactions(
    session_factory: sessionmaker, session_id: int
) -> List[Interaction]:
    """Retrieve all interactions for a specific session."""
    db_session = session_factory()
    
    try:
        return db_session.query(Interaction).filter_by(session_id=session_id).all()
    finally:
        db_session.close()

def get_user_sessions(
    session_factory: sessionmaker, user_id: str
) -> List[Session]:
    """Retrieve all sessions for a specific user."""
    db_session = session_factory()
    
    try:
        return db_session.query(Session).filter_by(user_id=user_id).all()
    finally:
        db_session.close()

def delete_user_data(session_factory: sessionmaker, user_id: str) -> None:
    """Delete all data associated with a user (GDPR compliance)."""
    db_session = session_factory()
    
    try:
        # This will cascade delete all associated interactions
        db_session.query(Session).filter_by(user_id=user_id).delete()
        db_session.commit()
    finally:
        db_session.close()


def store_entities(
        session_factory: sessionmaker,
        interaction_id: int,
        entities: Dict[str, Any]
) -> List[Entity]:
    """Store entities extracted from conversation in the database."""
    db_session = session_factory()
    stored_entities = []

    try:
        for entity_type, entity_value in entities.items():
            # Skip empty values
            if entity_value is None or entity_value == "":
                continue

            # Handle lists of values (e.g., multiple people)
            if isinstance(entity_value, list):
                for value in entity_value:
                    if value is not None and value != "":
                        entity = Entity(
                            interaction_id=interaction_id,
                            entity_type=entity_type,
                            entity_value=str(value)
                        )
                        db_session.add(entity)
                        stored_entities.append(entity)
            else:
                entity = Entity(
                    interaction_id=interaction_id,
                    entity_type=entity_type,
                    entity_value=str(entity_value)
                )
                db_session.add(entity)
                stored_entities.append(entity)

        db_session.commit()

        # Create detached copies
        result = []
        for entity in stored_entities:
            db_session.refresh(entity)
            result.append(Entity(
                id=entity.id,
                interaction_id=entity.interaction_id,
                entity_type=entity.entity_type,
                entity_value=entity.entity_value
            ))

        return result
    except Exception as e:
        db_session.rollback()
        print(f"Error storing entities: {str(e)}")
        return []
    finally:
        db_session.close()


def get_interaction_entities(
        session_factory: sessionmaker, interaction_id: int
) -> List[Entity]:
    """Retrieve all entities for a specific interaction."""
    db_session = session_factory()

    try:
        return db_session.query(Entity).filter_by(interaction_id=interaction_id).all()
    finally:
        db_session.close()


def get_all_session_entities(
        session_factory: sessionmaker, session_id: int
) -> List[Entity]:
    """Retrieve all entities from all interactions in a session."""
    db_session = session_factory()

    try:
        # Query interactions in the session first
        interaction_ids = [
            interaction.id for interaction in
            db_session.query(Interaction).filter_by(session_id=session_id).all()
        ]

        # Then query entities associated with those interactions
        if interaction_ids:
            return db_session.query(Entity).filter(Entity.interaction_id.in_(interaction_ids)).all()
        return []
    finally:
        db_session.close()


def update_interaction_priority(
        session_factory: sessionmaker, interaction_id: int, priority: bool
) -> None:
    """Update the priority status of an interaction."""
    db_session = session_factory()

    try:
        interaction = db_session.query(Interaction).filter_by(id=interaction_id).first()
        if interaction:
            interaction.priority = priority
            db_session.commit()
    finally:
        db_session.close()

def get_all_sessions(session_factory: sessionmaker) -> List[Session]:
    """Retrieve all sessions from the database."""
    db_session = session_factory()
    
    try:
        return db_session.query(Session).order_by(Session.start_time.desc()).all()
    finally:
        db_session.close()

def get_session_entities(session_factory: sessionmaker, session_id: int) -> List[Entity]:
    """Retrieve all entities for a specific session."""
    db_session = session_factory()
    
    try:
        # First get all interaction IDs for this session
        interaction_ids = [
            interaction.id for interaction in
            db_session.query(Interaction).filter_by(session_id=session_id).all()
        ]
        
        # Then get all entities associated with these interactions
        return db_session.query(Entity).filter(Entity.interaction_id.in_(interaction_ids)).all()
    finally:
        db_session.close()