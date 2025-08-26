# memory.py — simple vector memory service
import os
import json
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10004
MEMORY_FILE = "data/memory_vectors.json" # Relative path
EMBEDDING_MODEL = "text-embedding-004"

def get_embedding(text):
    try:
        result = genai.embed_content(model=f"models/{EMBEDDING_MODEL}", content=text, task_type="RETRIEVAL_DOCUMENT")
        return result['embedding']
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return []

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_memory(memory):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f)

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        l = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")

        if self.path == "/_py/add":
            text_to_add = data.get("text", "")
            doc_id = data.get("id", "")
            if not text_to_add or not doc_id:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"text and id are required"}'); return

            embedding = get_embedding(text_to_add)
            if not embedding:
                self.send_response(500); self.end_headers(); self.wfile.write(b'{"error":"Failed to generate embedding"}'); return
            
            memory = load_memory()
            memory = [entry for entry in memory if entry.get("id") != doc_id]
            memory.append({"id": doc_id, "text": text_to_add, "embedding": embedding})
            save_memory(memory)
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "entries": len(memory)}).encode("utf-8"))

        elif self.path == "/_py/query":
            query_text = data.get("query", "")
            top_k = int(data.get("top_k", 3))
            if not query_text:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"query is required"}'); return

            query_embedding = get_embedding(query_text)
            if not query_embedding:
                self.send_response(500); self.end_headers(); self.wfile.write(b'{"error":"Failed to generate query embedding"}'); return
            
            memory = load_memory()
            if not memory:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"results": []}).encode("utf-8")); return

            scores = [(cosine_similarity(query_embedding, entry["embedding"]), entry["text"]) for entry in memory if "embedding" in entry and entry["embedding"]]
            scores.sort(key=lambda x: x[0], reverse=True)
            
            results = [{"score": float(score), "text": text} for score, text in scores[:top_k]]
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"results": results}).encode("utf-8"))

        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
