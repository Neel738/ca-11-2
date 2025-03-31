import os
import sqlite3
import sqlite_vec
from sqlite_vec import serialize_float32
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Currently using openai's embeddings because they're fast & cheap, but we can replace if need
# Artistic inspiration: https://towardsdatascience.com/retrieval-augmented-generation-in-sqlite/
class RAG:
    def __init__(self, db_path: str, embedding_dim: int = 1536):
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None
        self.setup_db()

    def make_connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    def setup_db(self):
        try:
            conn = self.make_connect()
            conn.execute(f'CREATE VIRTUAL TABLE IF NOT EXISTS interaction_embeddings USING vec0(embedding float[{self.embedding_dim}], +interaction_id INTEGER, +session_id INTEGER, +transcript TEXT)')
            conn.commit()
            conn.close()
        except Exception as e:
            print("Exception in setup_db", e)

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not self.client or not text or text.strip() == "": return None
        try:
            response = self.client.embeddings.create(model="text-embedding-3-small", input=text)
            return response.data[0].embedding
        except Exception as e:
            print("Exception in generate_embedding:", e)
            return None

    # Store the embeddings per segment with relevant info
    def store_interaction_embedding(self, session_id: int, interaction_id: int, transcript: str) -> bool:
        embedding = self.generate_embedding(transcript)
        if not embedding: return False
        try:
            conn = self.make_connect()
            conn.execute('INSERT INTO interaction_embeddings (embedding, interaction_id, session_id, transcript) VALUES (?, ?, ?, ?)',
                (serialize_float32(embedding), interaction_id, session_id, transcript))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print("Exception in store_interaction_embedding:", e)
            return False

    def query_vector_db(self, query: str, limit: int):
        query_embedding = self.generate_embedding(query)
        if not query_embedding: return []
        try:
            conn = self.make_connect()
            rows = conn.execute("SELECT interaction_id, session_id, transcript, distance FROM interaction_embeddings WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (serialize_float32(query_embedding), limit)).fetchall()
            conn.close()
            return rows
        except Exception as e:
            print("Exception in query_vector_db:", e)
            return []


    # Retrieve memories with full info
    def retrieve_relevant_interactions(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        return [{'interaction_id': r[0], 'session_id': r[1], 'transcript': r[2], 'similarity': r[3]}
                for r in self.query_vector_db(query, limit)]


    def get_context_for_query(self, query: str, limit: int = 3) -> str:
        interactions = self.retrieve_relevant_interactions(query, limit)
        if not interactions: return "No relevant past interactions found."
        return "\n\n".join([f"Memory {i}: {interaction['transcript']}"
                           for i, interaction in enumerate(interactions, 1)])

    # Retrieve memories in a more textual format
    def get_relevant_memories_for_prompt(self, query: str, limit: int = 3,
                                        prefix: str = "Relevant memories for the give prompt:") -> str:
        rows = self.query_vector_db(query, limit)
        if not rows: return ""

        memories = [f"• {transcript}" for _, _, transcript, _ in rows]
        return f"{prefix}\n\n" + "\n\n".join(memories)

def initialize_rag(db_path: str) -> Optional[RAG]:
    try:
        return RAG(db_path)
    except Exception as e:
        print(f"Error initializing RAG: {e}")
        return None