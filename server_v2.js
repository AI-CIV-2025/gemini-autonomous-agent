// server_v2.js - Enhanced with selected improvements
const express = require('express');
const { execFile } = require('child_process');
const fs = require('fs');
const fse = require('fs-extra');
const path = require('path');
const axios = require('axios');

const PORT = process.env.PORT || 10000;
const MODEL = process.env.MODEL_GEMINI || 'gemini-1.5-pro-latest';
const AUTO_THRESHOLD = parseFloat(process.env.AUTO_APPROVE_RISK_THRESHOLD || "0.4");
const MAX_STEPS = parseInt(process.env.MAX_APPROVED_STEPS_PER_LOOP || "7");

const ROOT = __dirname;
const DATA = (...p) => path.join(ROOT, 'data', ...p);
const SITE = (...p) => path.join(ROOT, 'site', ...p);
const ARTIFACTS = (...p) => path.join(DATA('artifacts'), ...p);

const STATE_FILE = DATA('system_state.json');
const MISSION_FILE = DATA('current_mission.md');
const DEFAULT_MISSION = "Your primary mission is to maintain and improve the public dashboard at /site. Keep it simple, fast, and informative.";

// Import failure database
const { FailureDB } = require('./failure_db.js');
const failureDB = new FailureDB();

const app = express();
app.use(express.json({ limit: '10mb' }));
app.use(express.static(SITE()));

let loopCounter = 0;

// --- Agent Service Clients ---

async function geminiPlan(context) {
    const { data } = await axios.post('http://127.0.0.1:10005/_py/plan', { model: MODEL, context }, { timeout: 120000 });
    return data;
}

async function geminiReview(plan) {
    const { data } = await axios.post('http://127.0.0.1:10001/_py/review', { model: MODEL, ...plan }, { timeout: 120000 });
    return data;
}

async function geminiReflect(prompt) {
    const { data } = await axios.post('http://127.0.0.1:10002/_py/reflect', { model: MODEL, prompt }, { timeout: 120000 });
    return data;
}

async function geminiStrategize(prompt) {
    const { data } = await axios.post('http://127.0.0.1:10003/_py/strategize', { model: MODEL, prompt }, { timeout: 180000 });
    return data;
}

async function systemAgentImprove(trigger) {
    try {
        const { data } = await axios.post('http://127.0.0.1:10006/_py/improve', { trigger }, { timeout: 300000 });
        return data;
    } catch (e) {
        console.error("System agent failed:", e.message);
        return null;
    }
}

async function memoryAdd(id, text) {
    try {
        await axios.post('http://127.0.0.1:10004/_py/add', { id, text });
    } catch (e) {
        console.error("Failed to add to memory:", e.message);
    }
}

async function memoryQuery(query, top_k = 3) {
    try {
        const { data } = await axios.post('http://127.0.0.1:10004/_py/query', { query, top_k });
        return data.results || [];
    } catch (e) {
        console.error("Failed to query memory:", e.message);
        return [];
    }
}

// --- Logarithmic Retention (Improvement #2) ---
async function logarithmicCleanup(currentLoopId) {
    const keepLoops = new Set([1]);
    let n = 2;
    while (n < currentLoopId) {
        keepLoops.add(n);
        n *= 2;
    }
    
    // Also keep last 10 loops
    for (let i = Math.max(1, currentLoopId - 10); i <= currentLoopId; i++) {
        keepLoops.add(i);
    }
    
    // Delete artifacts not in keep list
    const allArtifacts = await fs.promises.readdir(ARTIFACTS());
    for (const file of allArtifacts) {
        const match = file.match(/^(\d+)_/);
        if (match) {
            const loopId = parseInt(match[1]);
            if (!keepLoops.has(loopId)) {
                await fse.remove(ARTIFACTS(file));
            }
        }
    }
}

// --- Self-Healing Filesystem (Improvement #6) ---
async function autoCleanup() {
    // Count artifacts
    const artifacts = await fs.promises.readdir(ARTIFACTS());
    if (artifacts.length > 1000) {
        // Keep only most recent 100
        const sorted = artifacts.sort((a, b) => {
            const aTime = fs.statSync(ARTIFACTS(a)).mtime;
            const bTime = fs.statSync(ARTIFACTS(b)).mtime;
            return bTime - aTime;
        });
        
        for (let i = 100; i < sorted.length; i++) {
            await fse.remove(ARTIFACTS(sorted[i]));
        }
        console.log(`Auto-cleaned ${sorted.length - 100} old artifacts`);
    }
    
    // Check site size
    const siteSize = await getDirSize(SITE());
    if (siteSize > 100 * 1024 * 1024) { // 100MB
        // Compress old loop files
        const loopFiles = await fs.promises.readdir(SITE('loops'));
        const oldFiles = loopFiles.filter(f => {
            const stat = fs.statSync(SITE('loops', f));
            return (Date.now() - stat.mtime) > 86400000; // Older than 1 day
        });
        
        for (const file of oldFiles) {
            await fse.remove(SITE('loops', file));
        }
        console.log(`Auto-cleaned ${oldFiles.length} old loop files`);
    }
}

async function getDirSize(dirPath) {
    let size = 0;
    const files = await fs.promises.readdir(dirPath, { withFileTypes: true });
    for (const file of files) {
        const filePath = path.join(dirPath, file.name);
        if (file.isDirectory()) {
            size += await getDirSize(filePath);
        } else {
            const stat = await fs.promises.stat(filePath);
            size += stat.size;
        }
    }
    return size;
}

// --- Enhanced Executor with Failure Tracking ---
async function runSteps(steps) {
    console.log(`Executing ${steps.length} approved steps via run_steps.sh...`);
    
    // Check failure patterns before execution (Improvement #3)
    const filteredSteps = [];
    for (const step of steps) {
        const [shouldSkip, reason] = failureDB.should_skip(step.bash);
        if (shouldSkip) {
            console.log(`Skipping step due to failure pattern: ${reason}`);
        } else {
            filteredSteps.push(step);
        }
    }
    
    if (filteredSteps.length === 0) {
        return { success: [], failed: [], final_report_md: "All steps skipped due to known failure patterns." };
    }
    
    return new Promise((resolve, reject) => {
        const stepsJson = JSON.stringify(filteredSteps);
        const child = execFile('./run_steps.sh', [stepsJson], {
            shell: '/bin/bash',
            cwd: ROOT,
            timeout: 600000
        }, (error, stdout, stderr) => {
            try {
                const results = JSON.parse(stdout);
                
                // Track failures (Improvement #3)
                if (results.failed && results.failed.length > 0) {
                    for (const failure of results.failed) {
                        failureDB.learn_failure(
                            failure.bash || "",
                            failure.stderr || "Unknown error",
                            failure.title || ""
                        );
                    }
                }
                
                resolve(results);
            } catch (parseError) {
                console.error("Failed to parse JSON from run_steps.sh output:", parseError);
                reject(new Error("Failed to parse executor output."));
            }
        });
    });
}

// --- Main Loop ---
async function oneLoop() {
    loopCounter++;
    const loopId = Date.now();
    console.log(`--- Starting Loop ${loopCounter} (${loopId}) ---`);
    
    // Auto cleanup before starting (Improvement #6)
    await autoCleanup();
    
    // System agent every 32 loops
    if (loopCounter % 32 === 0) {
        console.log("Triggering system agent for scheduled improvement...");
        const improvement = await systemAgentImprove("scheduled_32_loops");
        if (improvement) {
            console.log("System improvements applied:", improvement.diagnosis);
        }
    }
    
    await fse.ensureDir(ARTIFACTS());
    await fse.ensureDir(DATA('reflections'));
    await fse.ensureDir(DATA('tool_requests'));
    await fse.ensureDir(DATA('system_agent_requests'));
    await fse.ensureDir(SITE('loops'));

    await fse.outputJson(STATE_FILE, { status: 'running', loopId, startTime: loopId });

    try {
        const mission = (await fse.readFile(MISSION_FILE, 'utf8').catch(() => DEFAULT_MISSION));
        const relevantMemories = await memoryQuery(mission, 3);
        const recentReflections = (await fs.promises.readdir(DATA('reflections'))).sort().reverse().slice(0, 2);
        const recentReports = (await fs.promises.readdir(ARTIFACTS())).filter(f => f.endsWith('_report.md')).sort().reverse().slice(0, 5);

        const context = `
Current Mission: ${mission}
Loop Number: ${loopCounter}
---
Relevant long-term memories:
${relevantMemories.map(m => `- ${m.text.substring(0, 200)}...`).join('\n') || 'None'}
---
Recent reflections (learnings from past loops):
${(await Promise.all(recentReflections.map(f => fse.readFile(DATA('reflections', f), 'utf8')))).join('\n---\n') || 'None'}
---
Recent reports (actions taken):
${recentReports.join('\n') || 'None'}
---
Known failure patterns to avoid:
${failureDB.get_failure_summary()}`;

        const plan = await geminiPlan(context);
        await fse.outputJson(ARTIFACTS(`${loopId}_plan.json`), plan);

        const review = await geminiReview(plan);
        await fse.outputJson(ARTIFACTS(`${loopId}_review.json`), review);

        const originalStepsBash = plan.steps.map(s => `# ${s.title}\n${s.bash}`).join('\n\n');
        const approvedStepsBash = review.approved_steps.map(s => `# ${s.title}\n${s.bash}`).join('\n\n');
        const planDiff = `--- Original Plan ---\n${originalStepsBash}\n\n+++ Approved Plan +++\n${approvedStepsBash}`;
        await fse.outputFile(ARTIFACTS(`${loopId}_plan_review.diff`), planDiff);

        const approved = (review.approved_steps || [])
            .filter(s => (s.risk && typeof s.risk.score === 'number' ? s.risk.score : 1) <= AUTO_THRESHOLD)
            .slice(0, MAX_STEPS);

        const executionResults = await runSteps(approved);
        const reportPath = ARTIFACTS(`${loopId}_report.md`);
        await fse.outputFile(reportPath, executionResults.final_report_md || "No execution report was generated.");

        const reflectPrompt = `
Plan Summary:\n${plan.spec_md}\n
Reviewer Summary:\n${review.summary_md}\n
Execution Report:\n${executionResults.final_report_md}

Provide a reflection with these EXACT sections (30 words max each):
1. KEY LESSON: The single most important thing learned
2. AVOID: What failed or should not be repeated
3. NEXT ACTION: One specific thing to try next loop
`;
        const reflection = await geminiReflect(reflectPrompt);
        const reflectionPath = DATA('reflections', `${loopId}_reflection.md`);
        await fse.outputFile(reflectionPath, reflection.reflection_md);

        await memoryAdd(`report_${loopId}`, executionResults.final_report_md);
        await memoryAdd(`reflection_${loopId}`, reflection.reflection_md);

        await updateSite(loopId);
        
        // Logarithmic cleanup after each loop (Improvement #2)
        await logarithmicCleanup(loopCounter);

    } catch (error) {
        console.error(`Loop ${loopId} failed with error:`, error);
        await fse.outputFile(ARTIFACTS(`${loopId}_error.log`), error.stack);
        
        // Request system agent for hairy issues
        if (error.message.includes("timeout") || error.message.includes("parse")) {
            console.log("Requesting system agent for error resolution...");
            await systemAgentImprove(`error: ${error.message.substring(0, 100)}`);
        }
    } finally {
        console.log(`--- Finished Loop ${loopId} ---`);
        await fse.outputJson(STATE_FILE, { status: 'idle', lastLoopId: loopId, endTime: Date.now() });
    }
}

// --- Site Generation ---
async function updateSite(loopId) {
    console.log("Updating site...");
    const loopsDir = SITE('loops');
    await fse.ensureDir(loopsDir);

    const plan = await fse.readJson(ARTIFACTS(`${loopId}_plan.json`)).catch(()=>({spec_md:''}));
    const review = await fse.readJson(ARTIFACTS(`${loopId}_review.json`)).catch(()=>({summary_md:''}));
    const diff = await fse.readFile(ARTIFACTS(`${loopId}_plan_review.diff`), 'utf8').catch(()=>'');
    const report = await fse.readFile(ARTIFACTS(`${loopId}_report.md`), 'utf8').catch(()=>'');
    const reflection = await fse.readFile(DATA('reflections', `${loopId}_reflection.md`), 'utf8').catch(()=>'');

    const loopPageHtml = `
      <h1>Loop ${new Date(loopId).toLocaleString()}</h1>
      <h2>Mission</h2><pre>${plan.spec_md}</pre>
      <h2>Plan vs. Approved Diff</h2><pre>${diff}</pre>
      <h2>Reviewer's Summary</h2><div>${review.summary_md}</div>
      <h2>Execution Report</h2><pre>${report}</pre>
      <h2>Reflection</h2><div>${reflection}</div>
    `;
    await fse.outputFile(path.join(loopsDir, `${loopId}.html`), loopPageHtml);

    const allLoopIds = (await fse.readdir(loopsDir)).map(f => f.replace('.html', '')).sort((a, b) => b - a);
    
    const indexHtml = `
      <!DOCTYPE html><html lang="en"><head><title>Gemini Agent Dashboard</title></head><body>
        <h1>Autonomous Agent Loop Telemetry</h1>
        <p>Loop Counter: ${loopCounter} | System Agent Runs: ${Math.floor(loopCounter / 32)}</p>
        <table><thead><tr><th>Timestamp</th><th>Loop ID</th><th>Details</th></tr></thead><tbody>
            ${allLoopIds.slice(0, 50).map(id => `
              <tr>
                <td>${new Date(parseInt(id)).toLocaleString()}</td>
                <td>${id}</td>
                <td><a href="/loops/${id}.html">View Details</a></td>
              </tr>`).join('')}
          </tbody></table></body></html>`;
    await fse.outputFile(SITE('index.html'), indexHtml);
    console.log("Site updated.");
}

// --- API Endpoints ---
app.post('/cron/loop', async (req, res) => {
    const state = await fse.readJson(STATE_FILE).catch(() => ({ status: 'idle' }));
    if (state.status === 'running') {
        console.log("Loop is already running. Skipping.");
        return res.status(202).send("Loop already running.");
    }
    oneLoop();
    res.status(202).send("Loop started.");
});

app.post('/cron/strategize', async (req, res) => {
    console.log("--- Running Strategist ---");
    const reflections = (await fs.promises.readdir(DATA('reflections'))).sort().reverse().slice(0, 10);
    const reports = (await fs.promises.readdir(ARTIFACTS())).filter(f => f.endsWith('_report.md')).sort().reverse().slice(0, 20);
    const prompt = `Recent Reflections (last 10):\n${(await Promise.all(reflections.map(f => fse.readFile(DATA('reflections', f), 'utf8')))).join('\n---\n')}\n\nRecent Reports (last 20 files):\n${reports.join('\n')}\n\nBased on all of this, define the next primary mission. IMPORTANT: Keep it simple and concrete. Avoid recursive or self-referential goals.`;
    const result = await geminiStrategize(prompt);
    await fse.outputFile(MISSION_FILE, result.mission_md);
    console.log("New mission set by strategist.");
    res.status(200).send("Strategist run complete.");
});

app.post('/system-agent/trigger', async (req, res) => {
    const { reason } = req.body;
    console.log(`System agent manually triggered: ${reason}`);
    const result = await systemAgentImprove(reason || "manual_trigger");
    res.status(200).json(result || { error: "System agent failed" });
});

// --- Server Start ---
app.listen(PORT, async () => {
    await fse.ensureDir(DATA());
    await fse.ensureDir(SITE());
    console.log(`Server v2 listening on port ${PORT} with improvements enabled`);
});