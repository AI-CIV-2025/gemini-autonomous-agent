# 🤖 Gemini Autonomous Agent - Self-Improving AI System

> An anti-fragile, self-modifying autonomous agent system that improves over time and can run indefinitely without human intervention.

[![GitHub](https://img.shields.io/badge/GitHub-AI--CIV--2025-blue)](https://github.com/AI-CIV-2025/gemini-autonomous-agent)
[![Docker](https://img.shields.io/badge/Docker-Ready-green)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/Powered%20by-Gemini-orange)](https://ai.google.dev/)

## 🌟 Key Features

### Core Architecture
- **5 Specialized AI Agents**: Planner, Reviewer, Reflector, Strategist, and Memory
- **System Agent**: Meta-agent that modifies the codebase to fix issues (runs every 32 loops)
- **Docker Containerized**: Fully isolated, safe execution environment
- **Web Dashboard**: Real-time telemetry and monitoring

### Infinite Runtime Capabilities (v2)
- **Intelligent Memory Compression**: Compresses 100 memories → 1 lesson learned
- **Logarithmic Retention**: Keeps loops 1,2,4,8,16,32... (exponential sampling)
- **Failure Pattern Database**: Never repeats the same mistake >3 times
- **Mission Stability Anchor**: Prevents goal drift with immutable core mission
- **Self-Healing Filesystem**: Automatic cleanup when resources exceed thresholds
- **30-Word Reflections**: Compressed insights (KEY LESSON / AVOID / NEXT ACTION)

## 📊 Performance Metrics

Based on simulations (see `SIMULATION_V2.md`):

| Metric | Early (Loop 10) | Mature (Loop 100) | Long-term (Loop 1000+) |
|--------|-----------------|-------------------|------------------------|
| Success Rate | 80% | 99% | 99.9% |
| Disk Usage | 45KB | 200KB | 300KB (stable) |
| Memory Entries | 10 | 35 + 5 lessons | 50 + 20 principles |
| Complexity | Growing | Stabilizing | Minimalist |

## 🚀 Quick Start

### Prerequisites
- Docker installed and running
- Google AI (Gemini) API key

### 1. Clone the Repository
```bash
git clone https://github.com/AI-CIV-2025/gemini-autonomous-agent.git
cd gemini-autonomous-agent
```

### 2. Create Environment File
```bash
cat > .env << EOF
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional configuration
MODEL_GEMINI=gemini-1.5-pro-latest
AUTO_APPROVE_RISK_THRESHOLD=0.4
MAX_APPROVED_STEPS_PER_LOOP=7
EOF
```

### 3. Run Basic Version
```bash
# Build and run original version
docker build -t gemini-agent .
docker run -d -p 10000:10000 --env-file .env --name gemini-agent gemini-agent
```

### 4. Run Enhanced Version (Recommended)
```bash
# Build and run v2 with infinite runtime improvements
docker build -t gemini-agent-v2 -f Dockerfile_v2 .
docker run -d -p 10000-10006:10000-10006 --env-file .env --name gemini-agent-v2 gemini-agent-v2
```

### 5. Trigger Agent Loops
```bash
# Start a single loop
curl -X POST http://localhost:10000/cron/loop

# Update mission (runs strategist)
curl -X POST http://localhost:10000/cron/strategize

# Manually trigger System Agent (v2 only)
curl -X POST http://localhost:10000/system-agent/trigger -d '{"reason":"manual"}'
```

### 6. View Dashboard
Open browser to: http://localhost:10000

## 🔄 How It Works

### Loop Cycle
1. **Plan**: Gemini creates bash commands to achieve mission
2. **Review**: Safety review and risk assessment of commands
3. **Execute**: Safe commands run in sandboxed environment
4. **Reflect**: Learn from successes and failures
5. **Compress**: Every 100 memories → 1 lesson learned

### System Agent (Every 32 Loops)
1. Analyzes entire codebase
2. Reviews failure patterns
3. Generates patches to fix issues
4. Self-modifies the system
5. Documents improvements

## 📁 Project Structure

```
gemini-autonomous-agent/
├── server.js           # Original orchestrator
├── server_v2.js        # Enhanced with improvements
├── planner.py          # Creates action plans
├── reviewer.py         # Reviews for safety
├── reflector.py        # Learns from outcomes
├── reflector_v2.py     # 30-word compression
├── strategist.py       # Sets high-level goals
├── strategist_v2.py    # Mission-anchored version
├── memory.py           # Vector memory storage
├── memory_v2.py        # With compression
├── system_agent.py     # Self-modification engine
├── failure_db.py       # Pattern tracking
├── run_steps.sh        # Secure executor
├── exec_policy.json    # Command whitelist
└── Dockerfile_v2       # Enhanced container
```

## 🧠 Emergent Behaviors

After running for extended periods, the agent develops:

1. **Recipe Book**: Creates reusable command patterns
2. **Style Consistency**: Develops preferred coding patterns
3. **Predictive Avoidance**: Prevents failures before attempting
4. **Self-Documentation**: Writes guides for future iterations
5. **Philosophical Maturity**: Converges on simplicity as optimal

## 📈 Expected Evolution

- **Loops 1-10**: Learning phase, 20% failure rate
- **Loops 10-50**: Optimization phase, failures drop to 5%
- **Loops 50-200**: Stable productivity, <1% failures
- **Loops 200+**: Self-maintaining steady state
- **Loops 1000+**: Philosophical convergence, 0.01% failures

## ⚙️ Configuration

### Environment Variables
- `GOOGLE_API_KEY`: Your Gemini API key (required)
- `MODEL_GEMINI`: Model to use (default: gemini-1.5-pro-latest)
- `AUTO_APPROVE_RISK_THRESHOLD`: Max risk score for auto-approval (0.0-1.0)
- `MAX_APPROVED_STEPS_PER_LOOP`: Max commands per loop

### Execution Policy
Edit `exec_policy.json` to control allowed commands:
```json
{
  "allow_bins": ["echo", "cat", "ls", "grep", ...],
  "allow_net_bins": ["curl", "wget"],
  "deny_patterns": ["rm -rf", "sudo", ...]
}
```

## 🔬 Simulations

See detailed simulations of long-term behavior:
- `simulation-report.md`: Original version (shows collapse)
- `SIMULATION_V2.md`: Enhanced version (achieves enlightenment)
- `improvements-for-infinite-runtime.md`: Technical improvements

## 🤝 Contributing

This is an experimental autonomous system. Contributions welcome for:
- Additional safety mechanisms
- Better memory compression algorithms
- More sophisticated System Agent capabilities
- Alternative execution policies

## ⚠️ Safety Notes

- Runs in Docker container for isolation
- All commands pass through safety review
- Filesystem operations restricted to `/app`
- Network access controlled by policy
- Automatic resource limits enforced

## 📜 License

MIT - See LICENSE file

## 🙏 Acknowledgments

- Powered by Google's Gemini API
- Inspired by autonomous agent research
- Built with anti-fragility principles

---

**"The agent essentially becomes a Zen master of bash scripting."** - From simulation results

For detailed technical information, see `IMPROVEMENTS.md` and simulation reports.