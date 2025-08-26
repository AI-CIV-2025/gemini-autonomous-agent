# reflector.py — short contemplation pass
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT=10002

SYSTEM="""You are a contemplative AI agent, reflecting on a completed work cycle to guide the next one.
Input: The plan, the review, and the results of the execution (successes and failures).

Your task is to write a short, crisp reflection in markdown.
Based on the full context, provide:
- 3 bullets on what we **learned** from this loop (e.g., "The `grep` command failed because we didn't check if the file existed first.").
- 3 bullets on **risks or opportunities** (e.g., "Risk: The planner is repeatedly suggesting a complex command that the reviewer keeps rejecting. Opportunity: We could simplify the approach by using two smaller commands instead.").
- 3 **next hypotheses** to test in the upcoming loops (e.g., "Hypothesis: Adding `set -e` to our shell scripts will make them fail faster and provide clearer error signals.").

Keep the total reflection to ~150 words. Be insightful and forward-looking.
"""

def reflect(prompt:str, model:str):
    m = genai.GenerativeModel(model)
    r = m.generate_content([
        {"role":"system","parts":[SYSTEM]},
        {"role":"user","parts":[prompt]}
    ])
    return {"reflection_md": r.text or "No reflection."}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/reflect":
            self.send_response(404); self.end_headers(); return
        l = int(self.headers.get("Content-Length",0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        model = data.get("model","gemini-1.5-pro-latest")
        prompt = data.get("prompt","")
        out = reflect(prompt, model)
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
