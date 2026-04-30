"""
Friday V2.2 :: Semantic Memory Layer
Powered by LanceDB. Enables long-term recall and contextual awareness.
"""
import os
import lancedb
import numpy as np
from pathlib import Path
from datetime import datetime
from sentence_transformers import SentenceTransformer

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
DB_PATH = FRIDAY_ROOT / "data" / "lancedb"
DB_PATH.mkdir(parents=True, exist_ok=True)

class VectorMemory:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.db = lancedb.connect(str(DB_PATH))
        self.model = SentenceTransformer(model_name)
        
        if "memories" not in self.db.table_names():
            # Create schema without dummy data
            import pyarrow as pa
            schema = pa.schema([
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("text", pa.string()),
                pa.field("category", pa.string()),
                pa.field("ts", pa.string())
            ])
            self.db.create_table("memories", schema=schema)
        self.table = self.db.open_table("memories")

    def remember(self, text: str, category: str = "general"):
        """Embed and store a new memory."""
        vec = self.model.encode(text)
        self.table.add([{
            "vector": vec,
            "text": text,
            "category": category,
            "ts": datetime.now().isoformat()
        }])

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Semantic search for relevant memories."""
        query_vec = self.model.encode(query)
        results = self.table.search(query_vec).limit(limit).to_list()
        # Clean output
        return [{"text": r["text"], "category": r["category"], "ts": r["ts"]} for r in results]

    def clear(self):
        """Wipe the table."""
        self.db.drop_table("memories")

if __name__ == "__main__":
    mem = VectorMemory()
    mem.remember("Bhargav prefers black coffee, no sugar.", category="preferences")
    print("Memory stored.")
