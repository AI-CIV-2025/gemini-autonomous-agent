# strategist_v2.py - Enhanced with mission stability anchor (Improvement #4)
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10003

# Immutable core mission that anchors all strategies
CORE_MISSION = "Maintain a simple, fast, informative dashboard at /site"

SYSTEM = f"""You are a CTO and strategist for an autonomous AI agent.
Your role is to run infrequently (e.g., once a day) to set the overall mission.

IMMUTABLE CONSTRAINT: Every mission must support the core mission: {CORE_MISSION}

Input: A collection of recent reports (what was done) and reflections (what was learned).

Your Job:
1. Analyze the overall progress, successes, and failures.
2. Identify the most important strategic direction for the next ~12-24 hours.
3. Write a new, concise mission statement (MAX 50 words).

RULES:
- Keep missions simple, concrete, and measurable
- AVOID recursive or self-referential goals (e.g., "improve our improvement process")
- AVOID abstract missions (e.g., "optimize optimization")
- PREFER specific targets (e.g., "Add response time metrics to dashboard")
- Always relate back to the core mission

Bad missions (DO NOT generate these):
- "Analyze our analysis capabilities"
- "Document the documentation system"
- "Improve how we improve"

Good missions:
- "Add a chart showing average loop execution time to the dashboard"
- "Fix the three most common error patterns in our logs"
- "Reduce dashboard page load time to under 2 seconds"

Output ONLY the markdown content for the new mission file. Be concise and clear.
"""

def validate_mission(mission_text):
    """Check if mission is recursive or too abstract"""
    recursive_terms = [
        "optimize optimization",
        "improve improvement", 
        "analyze analysis",
        "document documentation",
        "understand understanding",
        "process process",
        "system system"
    ]
    
    mission_lower = mission_text.lower()
    
    # Check for recursive patterns
    for term in recursive_terms:
        if term in mission_lower:
            return False, "Mission is recursive/self-referential"
    
    # Check for too many abstract words
    abstract_words = ["optimize", "enhance", "improve", "analyze", "understand", "investigate"]
    abstract_count = sum(1 for word in abstract_words if word in mission_lower)
    if abstract_count > 2:
        return False, "Mission is too abstract"
    
    # Check length
    if len(mission_text.split()) > 50:
        return False, "Mission is too long"
    
    return True, "Valid"

def strategize(prompt: str, model: str):
    m = genai.GenerativeModel(model)
    
    # Add core mission reminder to prompt
    enhanced_prompt = f"{prompt}\n\nREMEMBER: The core mission is '{CORE_MISSION}'. Your new mission must support this."
    
    r = m.generate_content([
        {"role": "system", "parts": [SYSTEM]},
        {"role": "user", "parts": [enhanced_prompt]}
    ])
    
    mission = r.text or "Mission unchanged."
    
    # Validate the mission
    is_valid, reason = validate_mission(mission)
    
    if not is_valid:
        print(f"Mission rejected ({reason}), reverting to core mission")
        mission = f"{CORE_MISSION}. Focus on stability and performance."
    
    return {"mission_md": mission}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/strategize":
            self.send_response(404); self.end_headers(); return
        l = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        model = data.get("model", "gemini-1.5-pro-latest")
        prompt = data.get("prompt", "")
        out = strategize(prompt, model)
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()