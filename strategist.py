# strategist.py — high-level goal-setting agent
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10003

SYSTEM = """You are a CTO and strategist for an autonomous AI agent.
Your role is to run infrequently (e.g., once a day) to set the overall mission.

Input: A collection of recent reports (what was done) and reflections (what was learned).

Your Job:
1.  Analyze the overall progress, successes, and failures.
2.  Identify the most important strategic direction for the next ~12-24 hours.
3.  Write a new, concise mission statement into a markdown file. This mission will guide the lower-level Planner agent.

Focus on high-level goals. Examples:
- "The site deployment is stable. The new mission is to analyze our own execution logs to find patterns in failures and propose improvements to our review process."
- "We have failed to deploy to Netlify three times. The primary mission is to diagnose and fix the Netlify deployment issue. All other tasks are secondary."
- "The core functionality is working. The new mission is to add a new section to the site dashboard showing system health metrics, like average loop time and failure rates."

Output ONLY the markdown content for the new mission file. Be concise and clear.
"""

def strategize(prompt: str, model: str):
    m = genai.GenerativeModel(model)
    r = m.generate_content([
        {"role": "system", "parts": [SYSTEM]},
        {"role": "user", "parts": [prompt]}
    ])
    return {"mission_md": r.text or "Mission unchanged."}

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
