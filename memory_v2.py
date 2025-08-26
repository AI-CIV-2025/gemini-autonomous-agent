# memory_v2.py - Enhanced with intelligent compression
import os
import json
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10004
MEMORY_FILE = "data/memory_vectors.json"
LESSONS_FILE = "data/compressed_lessons.json"
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

def compress_memories(memories):
    """Every 100 memories, compress old ones into lessons"""
    if len(memories) <= 100:
        return memories
    
    # Group similar memories by clustering
    old_memories = memories[:-50]  # Keep recent 50
    
    # Extract patterns and create compressed lesson
    patterns = extract_patterns(old_memories)
    lesson_text = f"Learned from {len(old_memories)} experiences: {patterns}"
    
    lesson = {
        "id": f"lesson_{int(time.time())}",
        "type": "compressed_lesson",
        "count": len(old_memories),
        "text": lesson_text,
        "embedding": get_embedding(lesson_text)
    }
    
    # Save compressed lessons separately
    lessons = load_lessons()
    lessons.append(lesson)
    save_lessons(lessons)
    
    # Return only recent memories + pointer to lessons
    return memories[-50:]

def extract_patterns(memories):
    """Use LLM to extract key patterns from memories"""
    if not memories:
        return "No patterns found"
    
    # Sample up to 10 memories for pattern extraction
    sample = memories[:10] if len(memories) > 10 else memories
    texts = [m.get("text", "")[:200] for m in sample]
    
    prompt = f"Extract the single most important pattern from these experiences in 20 words: {texts}"
    
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)
        return response.text[:100]  # Limit response length
    except:
        return "General operational patterns observed"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, 'r') as f:
        try:
            memories = json.load(f)
            # Auto-compress if too many
            if len(memories) > 100:
                memories = compress_memories(memories)
                save_memory(memories)
            return memories
        except json.JSONDecodeError:
            return []

def save_memory(memory):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f)

def load_lessons():
    if not os.path.exists(LESSONS_FILE):
        return []
    with open(LESSONS_FILE, 'r') as f:
        try:
            return json.load(f)
        except:
            return []

def save_lessons(lessons):
    os.makedirs(os.path.dirname(LESSONS_FILE), exist_ok=True)
    with open(LESSONS_FILE, 'w') as f:
        json.dump(lessons, f)

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
            
            # Search both memories and lessons
            memory = load_memory()
            lessons = load_lessons()
            all_searchable = memory + lessons
            
            if not all_searchable:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"results": []}).encode("utf-8")); return

            scores = [(cosine_similarity(query_embedding, entry["embedding"]), entry["text"]) 
                     for entry in all_searchable if "embedding" in entry and entry["embedding"]]
            scores.sort(key=lambda x: x[0], reverse=True)
            
            results = [{"score": float(score), "text": text} for score, text in scores[:top_k]]
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"results": results}).encode("utf-8"))

        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()