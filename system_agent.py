# system_agent.py - Meta-agent that improves the system itself
import os
import json
import glob
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
PORT = 10006

SYSTEM = """You are the System Agent - a meta-level AI that improves the autonomous agent system itself.

You have access to:
1. The complete codebase of all agents
2. Recent failure patterns and repeated mistakes  
3. System performance metrics
4. Ability to modify agent code to fix issues

Your responsibilities:
1. Analyze repeated failure patterns and fix their root causes
2. Optimize agent prompts when they produce poor results
3. Adjust safety policies that are too restrictive
4. Refactor code that causes performance issues
5. Add missing error handling

When you run (triggered every 32 loops OR on repeated failures):
- You receive the ENTIRE codebase concatenated
- You analyze systemic issues
- You generate SPECIFIC code patches to fix problems
- Your changes are conservative but effective

Output format:
{
  "diagnosis": "Brief description of main issues found",
  "patches": [
    {
      "file": "filename.py",
      "description": "What this fixes",
      "old_code": "exact string to replace",
      "new_code": "replacement code"
    }
  ],
  "new_features": [
    {
      "description": "New capability added",
      "rationale": "Why this helps"
    }
  ]
}

Rules:
- NEVER remove safety features
- NEVER allow dangerous commands
- Keep changes minimal and focused
- Test your logic mentally before suggesting patches
- Focus on fixing SYSTEMIC issues, not one-off problems
"""

def get_codebase_context():
    """Concatenate all agent code files"""
    codebase = {}
    code_files = [
        "server.js", "planner.py", "reviewer.py", "reflector.py", 
        "strategist.py", "memory_v2.py", "failure_db.py", "run_steps.sh"
    ]
    
    for filename in code_files:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                codebase[filename] = f.read()
    
    return codebase

def get_failure_patterns():
    """Load recent failure patterns"""
    if os.path.exists("data/failure_patterns.json"):
        with open("data/failure_patterns.json", 'r') as f:
            return json.load(f)
    return {}

def get_system_metrics():
    """Gather system performance metrics"""
    metrics = {
        "total_loops": len(glob.glob("data/artifacts/*_plan.json")),
        "disk_usage_mb": sum(os.path.getsize(f) for f in glob.glob("data/**/*", recursive=True)) / 1048576,
        "failure_patterns": len(get_failure_patterns()),
        "memory_size": len(json.load(open("data/memory_vectors.json"))) if os.path.exists("data/memory_vectors.json") else 0
    }
    
    # Calculate recent success rate
    recent_reports = sorted(glob.glob("data/artifacts/*_report.md"))[-10:]
    failures = sum(1 for r in recent_reports if "FAILED" in open(r).read())
    metrics["recent_failure_rate"] = failures / len(recent_reports) if recent_reports else 0
    
    return metrics

def apply_patches(patches):
    """Apply code patches to fix issues"""
    results = []
    for patch in patches:
        try:
            filename = patch["file"]
            if not os.path.exists(filename):
                results.append({"file": filename, "status": "not found"})
                continue
                
            with open(filename, 'r') as f:
                content = f.read()
            
            if patch["old_code"] in content:
                new_content = content.replace(patch["old_code"], patch["new_code"])
                with open(filename, 'w') as f:
                    f.write(new_content)
                results.append({"file": filename, "status": "patched", "description": patch["description"]})
            else:
                results.append({"file": filename, "status": "pattern not found"})
                
        except Exception as e:
            results.append({"file": patch["file"], "status": f"error: {e}"})
    
    return results

def analyze_and_improve(trigger_reason="scheduled"):
    """Main system improvement function"""
    print(f"System Agent activated: {trigger_reason}")
    
    # Gather context
    codebase = get_codebase_context()
    failures = get_failure_patterns()
    metrics = get_system_metrics()
    
    # Build prompt
    context = f"""
    TRIGGER REASON: {trigger_reason}
    
    SYSTEM METRICS:
    {json.dumps(metrics, indent=2)}
    
    REPEATED FAILURE PATTERNS:
    {json.dumps(failures, indent=2)[:5000]}  # Limit size
    
    CODEBASE:
    """
    
    for filename, code in codebase.items():
        context += f"\n\n=== {filename} ===\n{code[:3000]}..."  # Sample each file
    
    # Get AI analysis
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content([
        {"role": "system", "parts": [SYSTEM]},
        {"role": "user", "parts": [context]}
    ])
    
    try:
        result = json.loads(response.text)
    except:
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {
                "diagnosis": "Failed to parse system agent response",
                "patches": [],
                "new_features": []
            }
    
    # Apply patches
    if result.get("patches"):
        patch_results = apply_patches(result["patches"])
        result["patch_results"] = patch_results
    
    # Save improvement report
    report_file = f"data/system_improvements/{int(time.time())}_improvement.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_py/improve":
            self.send_response(404); self.end_headers(); return
            
        l = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(l).decode("utf-8") or "{}")
        
        trigger = data.get("trigger", "scheduled")
        result = analyze_and_improve(trigger)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()