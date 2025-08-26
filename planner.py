# planner.py — Gemini agent for generating a sequence of shell commands
import os
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10005

SYSTEM = """You are an expert AI planner. Your job is to break down a high-level mission into a series of small, concrete, and executable bash steps.

INPUT: A context string containing the current mission, long-term memories, recent reflections, and recent reports.

RULES:
1.  **Decomposition**: Break the mission into a logical sequence of `steps`. Each step must be a self-contained bash command.
2.  **Idempotency**: Prefer commands that are idempotent (running them multiple times has the same effect as running them once).
3.  **Simplicity**: Use simple, common shell commands. Avoid complex scripts or one-liners.
4.  **Filesystem**: Assume you are running in `/app`. All file paths should be relative to `/app`. Use `/app/data/artifacts` for temporary or output files.
5.  **Timeouts**: Suggest a reasonable `timeout_sec` for each step. 30-60 seconds for simple commands, up to 300 for more complex tasks like analysis.
6.  **Network**: Note if a step requires network access with `allow_net: true`. The executor policy may deny this.

OUTPUT: A strict JSON object with the following structure:
{
  "spec_md": "A concise, one-paragraph summary of your plan.",
  "todo_md": "A markdown checklist of the steps you are proposing.",
  "steps": [
    {
      "title": "A short, descriptive title for the step",
      "bash": "The single, complete bash command to execute",
      "cwd": "/app",
      "allow_net": false,
      "timeout_sec": 60
    }
  ]
}
"""

def plan(context: str, model: str):
    m = genai.GenerativeModel(model)
    r = m.generate_content([
        {"role": "system", "parts": [SYSTEM]},
        {"role": "user", "parts": [context]}
    ])
    text = r.text or "{}"
    try:
        clean_text = re.sub(r'```json\n?|\n?```', '', text.strip())
        out = json.loads(clean_text)
        out["steps"] = out.get("steps", [])
        return out
    except Exception as e:
        return {
            "spec_md": "Error: Failed to generate a valid plan.",
            "todo_md": f"- The planner agent failed to produce valid JSON.\n- Error: {e}\n- Raw output: {text}",
            "steps": []
        }

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/plan":
            self.send_response(404); self.end_headers(); return
        l = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        model = data.get("model", "gemini-1.5-pro-latest")
        context = data.get("context", "")
        out = plan(context, model)
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
