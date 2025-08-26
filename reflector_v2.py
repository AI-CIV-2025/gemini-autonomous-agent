# reflector_v2.py - Enhanced with 30-word compression (Improvement #9)
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10002

SYSTEM = """You are a contemplative AI agent, reflecting on a completed work cycle to guide the next one.

Your task is to write an EXTREMELY CONCISE reflection with EXACTLY these three sections:

1. **KEY LESSON** (max 30 words): The single most important thing learned from this loop
2. **AVOID** (max 30 words): What failed or should not be repeated 
3. **NEXT ACTION** (max 30 words): One specific, concrete action to try in the next loop

Format your response EXACTLY like this:
KEY LESSON: [your 30-word lesson here]
AVOID: [your 30-word warning here]  
NEXT ACTION: [your 30-word suggestion here]

Be specific and actionable. No fluff, no abstract statements.

Bad example (too vague):
KEY LESSON: We learned important things about system optimization
AVOID: Making mistakes with complex commands
NEXT ACTION: Try to improve the dashboard

Good example (specific):
KEY LESSON: Grep commands timeout on directories with 1000+ files. Use find with -maxdepth instead.
AVOID: Running find without limits in /app/data. It times out after 300 seconds consistently.
NEXT ACTION: Add execution time display to dashboard showing which commands are slowest.
"""

def reflect(prompt: str, model: str):
    m = genai.GenerativeModel(model)
    r = m.generate_content([
        {"role": "system", "parts": [SYSTEM]},
        {"role": "user", "parts": [prompt]}
    ])
    
    reflection_text = r.text or "No reflection generated."
    
    # Parse and enforce word limits
    lines = reflection_text.split('\n')
    compressed = []
    
    for line in lines:
        if line.startswith("KEY LESSON:") or line.startswith("AVOID:") or line.startswith("NEXT ACTION:"):
            # Extract the content after the label
            parts = line.split(':', 1)
            if len(parts) == 2:
                label = parts[0]
                content = parts[1].strip()
                words = content.split()
                
                # Enforce 30-word limit
                if len(words) > 30:
                    content = ' '.join(words[:30])
                
                compressed.append(f"{label}: {content}")
    
    # Ensure all three sections exist
    sections = {"KEY LESSON": False, "AVOID": False, "NEXT ACTION": False}
    for line in compressed:
        for section in sections:
            if line.startswith(section):
                sections[section] = True
    
    # Add missing sections with defaults
    if not sections["KEY LESSON"]:
        compressed.insert(0, "KEY LESSON: No specific lesson extracted from this loop.")
    if not sections["AVOID"]:
        compressed.insert(1, "AVOID: No specific failures to avoid identified.")
    if not sections["NEXT ACTION"]:
        compressed.append("NEXT ACTION: Continue with current approach.")
    
    final_reflection = '\n'.join(compressed[:3])  # Only keep the 3 required sections
    
    return {"reflection_md": final_reflection}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/reflect":
            self.send_response(404); self.end_headers(); return
        l = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        model = data.get("model", "gemini-1.5-pro-latest")
        prompt = data.get("prompt", "")
        out = reflect(prompt, model)
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()