from datetime import datetime, timedelta
import math
from typing import List

from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker

from database import Interaction, Entity


class ForgettingModel:
    """Memory manager with Ebbinghaus forgetting curve implementation."""

    ### placeholder forgetting model mostly
    def __init__(
            self,
            session_factory: sessionmaker,
            decay_factor: float = 0.1,
            retention_threshold: float = 0.3
    ):
        self.session_factory = session_factory
        self.decay_factor = decay_factor
        self.retention_threshold = retention_threshold

    def retention(self, age_hours: float, is_priority: bool = False) -> float:
        # Priority memories have greater strength (decay slower)
        strength = 5.0 if is_priority else 1.0
        retention = math.exp(-(self.decay_factor * age_hours) / strength)
        return min(1.0, max(0.0, retention))

    def forget_old_memories(self) -> int:
        """Remove interactions with retention below threshold."""
        db_session = self.session_factory()
        try:
            interactions = db_session.query(Interaction).all()
            to_forget = []

            # See for each memory if we want to keep it
            for interaction in interactions:
                if interaction.priority:
                    continue

                # Age in hours
                age_hours = (datetime.utcnow() - interaction.timestamp).total_seconds() / 3600
                retention = self.retention(age_hours, False)

                # If retention is below threshold, schedule for forgetting
                if retention < self.retention_threshold:
                    to_forget.append(interaction)

            # Delete entities and interactions
            count = 0
            for interaction in to_forget:
                db_session.query(Entity).filter(
                    Entity.interaction_id == interaction.id
                ).delete()
                db_session.delete(interaction)
                count += 1

            db_session.commit()
            return count
        except Exception as e:
            db_session.rollback()
            print(f"Error forgetting memories: {str(e)}")
            return 0
        finally:
            db_session.close()