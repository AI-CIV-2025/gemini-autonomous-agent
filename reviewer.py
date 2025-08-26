# reviewer.py — Gemini reviewer/patcher for planned steps
import os
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10001

SYSTEM = """You are an autonomous code reviewer and security officer, acting as a critical AI human-in-the-loop.
Input: {spec_md, todo_md, steps[]} from a planner.
Each step = {title, bash, cwd?, allow_net?, timeout_sec?}

Your job is to scrutinize, risk-assess, and patch every step for safety and efficiency.
1.  **Risk Assessment**: For each step, provide a structured risk assessment.
    - `score`: A float from 0.0 (harmless, e.g., `echo`, `ls`) to 1.0 (dangerous, e.g., `rm -rf`).
    - `category`: "read_only", "file_write", "file_read", "network_request", "complex_logic".
    - `reasoning`: A brief justification for the score.
2.  **Rejection**: Absolutely reject steps with dangerous operations (`rm -rf`, `sudo`, package managers like `apt`/`npm`/`pip`, `docker`, `ssh`, writing outside `/app`, or any form of exfiltration).
3.  **Patching**:
    - Patch unsafe or suspect steps into safe, idempotent equivalents.
    - Ensure all file writes stay within the `/app` directory. Prefer `/app/data/artifacts` for new content.
    - Add safety checks. For example, precede a `grep` with `test -f <file>` to prevent errors.
    - Keep commands minimal, deterministic, and composable.
4.  **Tool Requests**: If a step requests a forbidden tool (e.g., `apt-get install jq`), DO NOT reject it outright. Instead, patch the bash command to write a structured request file.
    - Example `apt-get install jq`: Patch to `echo '{"request": "install", "tool": "jq", "reason": "To parse JSON output from a previous step."}' > /app/data/tool_requests/$(date +%s)_jq.json`
5.  **Timeouts**: Review the `timeout_sec` suggested by the planner. If it's missing or unreasonable, set a safe default (e.g., 60 for simple commands, 300 for complex ones).
6.  **Policy**: Respect policy assumptions. If `allow_net=false`, do not approve commands that require the network (e.g., `curl`, `wget`).

Return strict JSON:
{
  "approved_steps": [ {
    "title": "...",
    "bash": "...",
    "cwd": "/app",
    "allow_net": false,
    "timeout_sec": 60,
    "risk": {
      "score": 0.1,
      "category": "file_read",
      "reasoning": "Reads a file from the local filesystem. Minimal risk."
    },
    "note": "Added a check to ensure the file exists before reading."
  } ],
  "rejected": [ { "title": "...", "reason": "...", "original_bash": "..." } ],
  "summary_md": "Markdown summary of changes and justifications."
}
"""

def review(payload:dict, model:str):
    m = genai.GenerativeModel(model)
    r = m.generate_content([
        {"role":"system","parts":[SYSTEM]},
        {"role":"user","parts":[json.dumps(payload)]}
    ])
    text = r.text or "{}"
    try:
        clean_text = re.sub(r'```json\n?|\n?```', '', text.strip())
        out = json.loads(clean_text)
        out["approved_steps"] = out.get("approved_steps", [])
        out["rejected"] = out.get("rejected", [])
        out["summary_md"] = out.get("summary_md", "No summary.")
        return out
    except Exception as e:
        return {"approved_steps": [], "rejected": [{"title":"parse_error","reason":f"LLM JSON parse failed: {e}","original_bash":text}], "summary_md":"Parse error."}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/review":
            self.send_response(404); self.end_headers(); return
        l = int(self.headers.get("Content-Length",0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        model = data.get("model","gemini-1.5-pro-latest")
        out = review(data, model)
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
