import pytest
import os
import shutil
import lancedb
import numpy as np

# Simple Mock Embedding (for TDD speed)
def mock_embed(text):
    return [0.1 if word in text.lower() else 0.0 for word in ["client", "whatsapp", "bot", "revenue"]] + [0.0]*380

def test_semantic_storage_and_recall():
    db_path = "/tmp/friday_test_db"
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    
    db = lancedb.connect(db_path)
    table = db.create_table("memories", data=[
        {"vector": mock_embed("First WhatsApp bot client signed"), "text": "Client A signed for 15k", "id": "1"},
        {"vector": mock_embed("Trading bot strategy changed to Mean Reversion"), "text": "Strategy: MR", "id": "2"}
    ])
    
    # Query: "Tell me about my clients"
    query_vec = mock_embed("clients")
    results = table.search(query_vec).limit(1).to_list()
    
    assert "Client A" in results[0]["text"]
    print("✅ Semantic Memory TDD: Recall successful.")

if __name__ == "__main__":
    test_semantic_storage_and_recall()
