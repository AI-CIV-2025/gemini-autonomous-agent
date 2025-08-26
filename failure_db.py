# failure_db.py - Pattern database for avoiding repeated mistakes
import json
import os
import re
from typing import Tuple, Optional

class FailureDB:
    def __init__(self, db_path="data/failure_patterns.json"):
        self.db_path = db_path
        self.patterns = self.load_patterns()
        
    def load_patterns(self) -> dict:
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_patterns(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump(self.patterns, f, indent=2)
    
    def extract_pattern(self, command: str) -> str:
        """Extract command pattern for matching"""
        # Remove specific paths/filenames but keep structure
        pattern = re.sub(r'/[\w\-\.]+', '/<PATH>', command)
        # Remove specific numbers but keep pattern
        pattern = re.sub(r'\d+', '<NUM>', pattern)
        # Keep first command as key identifier
        first_cmd = command.split()[0] if command.split() else command
        return f"{first_cmd}:{pattern[:100]}"  # Limit length
    
    def learn_failure(self, command: str, error: str, title: str = ""):
        """Record a failed command pattern"""
        pattern = self.extract_pattern(command)
        
        if pattern not in self.patterns:
            self.patterns[pattern] = {
                "command_example": command[:200],
                "error": error[:200],
                "count": 1,
                "titles": [title] if title else [],
                "lesson": f"Command pattern '{pattern[:50]}' fails with: {error[:100]}"
            }
        else:
            self.patterns[pattern]["count"] += 1
            if title and title not in self.patterns[pattern]["titles"]:
                self.patterns[pattern]["titles"].append(title)
        
        # Trigger system agent if pattern repeats 3+ times
        if self.patterns[pattern]["count"] == 3:
            self.request_system_agent(pattern)
        
        self.save_patterns()
    
    def should_skip(self, command: str) -> Tuple[bool, Optional[str]]:
        """Check if command matches a known failure pattern"""
        pattern = self.extract_pattern(command)
        
        if pattern in self.patterns and self.patterns[pattern]["count"] >= 3:
            lesson = self.patterns[pattern]["lesson"]
            return True, f"Skipping - known failure pattern (failed {self.patterns[pattern]['count']} times): {lesson}"
        
        return False, None
    
    def request_system_agent(self, pattern: str):
        """Create a request for system agent intervention"""
        request = {
            "type": "repeated_failure",
            "pattern": pattern,
            "details": self.patterns[pattern],
            "request": "System agent needed: repeated failure pattern detected"
        }
        
        request_file = f"data/system_agent_requests/{int(time.time())}_failure.json"
        os.makedirs(os.path.dirname(request_file), exist_ok=True)
        with open(request_file, 'w') as f:
            json.dump(request, f, indent=2)
        
        print(f"System agent requested for repeated failure: {pattern}")
    
    def get_failure_summary(self) -> str:
        """Get summary of all failure patterns for system agent"""
        if not self.patterns:
            return "No failure patterns recorded yet."
        
        summary = "Known Failure Patterns:\n"
        for pattern, details in self.patterns.items():
            if details["count"] >= 2:  # Only show repeated failures
                summary += f"- {pattern[:50]}: {details['count']} failures\n"
        
        return summary

# Global instance
failure_db = FailureDB()