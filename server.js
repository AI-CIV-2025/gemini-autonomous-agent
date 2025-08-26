// server.js
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
const DEFAULT_MISSION = "Your primary mission is to maintain and improve the public dashboard at /site. Ensure it's always up-to-date with the latest system activities. You may optionally deploy to Netlify if credentials are available. Prefer small, idempotent, and testable steps.";

const app = express();
app.use(express.json({ limit: '10mb' }));
app.use(express.static(SITE()));

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

// --- Core Executor ---
async function runSteps(steps) {
    console.log(`Executing ${steps.length} approved steps via run_steps.sh...`);
    return new Promise((resolve, reject) => {
        const stepsJson = JSON.stringify(steps);
        const child = execFile('./run_steps.sh', [stepsJson], {
            shell: '/bin/bash',
            cwd: ROOT,
            timeout: 600000 // 10 minute total timeout for the whole batch
        }, (error, stdout, stderr) => {
            if (error) {
                console.error(`run_steps.sh execution error: ${error.message}`);
                // Still try to parse stdout as it might contain partial results
            }
            if (stderr) {
                console.error(`run_steps.sh stderr: ${stderr}`);
            }
            try {
                const results = JSON.parse(stdout);
                resolve(results);
            } catch (parseError) {
                console.error("Failed to parse JSON from run_steps.sh output:", parseError);
                console.error("Raw stdout from run_steps.sh:", stdout);
                reject(new Error("Failed to parse executor output."));
            }
        });
    });
}


// --- Main Loop ---
async function oneLoop() {
    const loopId = Date.now();
    console.log(`--- Starting Loop ${loopId} ---`);
    await fse.ensureDir(ARTIFACTS());
    await fse.ensureDir(DATA('reflections'));
    await fse.ensureDir(DATA('tool_requests'));
    await fse.ensureDir(SITE('loops'));

    await fse.outputJson(STATE_FILE, { status: 'running', loopId, startTime: loopId });

    try {
        const mission = (await fse.readFile(MISSION_FILE, 'utf8').catch(() => DEFAULT_MISSION));
        const relevantMemories = await memoryQuery(mission, 3);
        const recentReflections = (await fs.promises.readdir(DATA('reflections'))).sort().reverse().slice(0, 2);
        const recentReports = (await fs.promises.readdir(ARTIFACTS())).filter(f => f.endsWith('_report.md')).sort().reverse().slice(0, 5);

        const context = `
Current Mission: ${mission}
---
Relevant long-term memories:
${relevantMemories.map(m => `- ${m.text.substring(0, 200)}...`).join('\n') || 'None'}
---
Recent reflections (learnings from past loops):
${(await Promise.all(recentReflections.map(f => fse.readFile(DATA('reflections', f), 'utf8')))).join('\n---\n') || 'None'}
---
Recent reports (actions taken):
${recentReports.join('\n') || 'None'}`;

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
`;
        const reflection = await geminiReflect(reflectPrompt);
        const reflectionPath = DATA('reflections', `${loopId}_reflection.md`);
        await fse.outputFile(reflectionPath, reflection.reflection_md);

        await memoryAdd(`report_${loopId}`, executionResults.final_report_md);
        await memoryAdd(`reflection_${loopId}`, reflection.reflection_md);

        await updateSite(loopId);

    } catch (error) {
        console.error(`Loop ${loopId} failed with error:`, error);
        await fse.outputFile(ARTIFACTS(`${loopId}_error.log`), error.stack);
    } finally {
        console.log(`--- Finished Loop ${loopId} ---`);
        await fse.outputJson(STATE_FILE, { status: 'idle', lastLoopId: loopId, endTime: Date.now() });
    }
}

// --- Site Generation (Telemetry Dashboard) ---
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
        <table><thead><tr><th>Timestamp</th><th>Loop ID</th><th>Details</th></tr></thead><tbody>
            ${allLoopIds.map(id => `
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
    const prompt = `Recent Reflections (last 10):\n${(await Promise.all(reflections.map(f => fse.readFile(DATA('reflections', f), 'utf8')))).join('\n---\n')}\n\nRecent Reports (last 20 files):\n${reports.join('\n')}\n\nBased on all of this, define the next primary mission.`;
    const result = await geminiStrategize(prompt);
    await fse.outputFile(MISSION_FILE, result.mission_md);
    console.log("New mission set by strategist.");
    res.status(200).send("Strategist run complete.");
});

// --- Server Start ---
app.listen(PORT, async () => {
    await fse.ensureDir(DATA());
    await fse.ensureDir(SITE());
    console.log(`Server listening on port ${PORT}`);
});
