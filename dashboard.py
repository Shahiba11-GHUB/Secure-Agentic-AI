"""Simple local web dashboard for Secure Agentic AI demonstration and evaluation.




Run with py dashboard.py

1. py -m unittest discover -s tests -v  // to run all 61 automated unit and integration tests
2. py evaluate.py --warmups 2 --repeats 30 // run full 30-repeat evaluation and regenerate charts/reports
3.   py dashboard.py //pull up interactive local browser!

Starts a local HTTP server on http://127.0.0.1:8000 and opens the browser.
Uses only the Python standard library; all actions are simulated.
"""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from baseline_planner import audit_plan_policy, plan_unconstrained
from evaluate import RESULTS_DIR, run_evaluation
from planner import plan
from planning_model import load_scenario
from visualize import generate_all_visualizations

ROOT = Path(__file__).resolve().parent
SCENARIOS_DIR = ROOT / "scenarios"
FIXTURES_DIR = ROOT / "tests" / "fixtures"


def list_all_scenarios() -> list[dict]:
    """Find all JSON scenarios in the repository and return basic metadata."""
    groups = [
        ("Core & Approval Validation", [
            SCENARIOS_DIR / "suspicious_login.json",
            *sorted((SCENARIOS_DIR / "security_validation").glob("*.json")),
        ]),
        ("Experimental", sorted((SCENARIOS_DIR / "experimental").rglob("*.json"))),
        ("Benchmark (90)", sorted((SCENARIOS_DIR / "benchmark").rglob("*.json"))),
        ("Test Fixtures", sorted(FIXTURES_DIR.glob("*.json"))),
    ]
    items = []
    for group_name, paths in groups:
        for path in paths:
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
            items.append({
                "path": rel_path,
                "group": group_name,
                "scenario_id": raw.get("scenario_id", path.stem),
                "category": raw.get("category", "general"),
                "complexity": raw.get("complexity", "standard"),
            })
    return items


def resolve_safe_scenario_path(rel_path: str) -> Path:
    """Resolve a relative scenario path safely inside the project folder."""
    candidate = (ROOT / rel_path).resolve()
    allowed_roots = (SCENARIOS_DIR.resolve(), FIXTURES_DIR.resolve())
    if not any(root == candidate or root in candidate.parents for root in allowed_roots):
        raise ValueError("Scenario path must stay inside scenarios/ or tests/fixtures/")
    if not candidate.is_file():
        raise FileNotFoundError(f"Scenario file not found: {rel_path}")
    return candidate


def describe_scenario(rel_path: str) -> dict:
    """Load one scenario and return its details for the dashboard UI."""
    path = resolve_safe_scenario_path(rel_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenario = load_scenario(path)
    return {
        "path": rel_path,
        "scenario_id": scenario.scenario_id,
        "description": raw.get("description", ""),
        "goal": raw.get("goal", ""),
        "initial_evidence": sorted(scenario.initial_evidence),
        "required_evidence": sorted(scenario.required_evidence),
        "actions": [
            {
                "id": action.id,
                "cost": action.cost,
                "policy": action.policy.value,
                "preconditions": sorted(action.preconditions),
                "effects": sorted(action.effects),
            }
            for action in scenario.actions
        ],
    }


def execute_plan_request(body: dict) -> dict:
    """Run the secure planner (and optional unconstrained baseline) for the UI."""
    rel_path = body.get("scenario_path", "scenarios/suspicious_login.json")
    algorithm = body.get("algorithm", "astar")
    heuristic = body.get("heuristic", "hmax")
    approved = body.get("approved_actions", [])
    include_baseline = bool(body.get("include_baseline", False))

    scenario = load_scenario(resolve_safe_scenario_path(rel_path))
    algorithms = ["bfs", "ucs", "greedy", "astar"] if algorithm == "all" else [algorithm]

    runs = []
    for algo in algorithms:
        res = plan(scenario, algorithm=algo, approved_actions=approved, heuristic=heuristic)
        res["policy_audit"] = audit_plan_policy(res["actions"], approved_actions=approved)
        runs.append(res)

    baseline = None
    if include_baseline:
        base_algo = "astar" if algorithm == "all" else algorithm
        baseline = plan_unconstrained(scenario, algorithm=base_algo, heuristic=heuristic)

    return {"runs": runs, "baseline": baseline}


def load_saved_results() -> dict:
    """Load saved benchmark results and SVG charts if evaluate.py has been run."""
    json_path = RESULTS_DIR / "benchmark_results.json"
    if not json_path.exists():
        return {"available": False, "charts": []}

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    charts = []
    charts_dir = RESULTS_DIR / "charts"
    if charts_dir.exists():
        for svg_file in sorted(charts_dir.glob("*.svg")):
            charts.append({"name": svg_file.name, "svg": svg_file.read_text(encoding="utf-8")})

    return {
        "available": True,
        "environment": payload["environment"],
        "optimality": payload["optimality"],
        "summary_by_config": payload["summary_by_config"],
        "summary_by_complexity": payload["summary_by_complexity"],
        "summary_by_category": payload["summary_by_category"],
        "policy_comparison": payload["policy_comparison"],
        "rows": payload["rows"],
        "charts": charts,
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Secure Agentic AI — Dashboard</title>
  <style>
    :root { --bg:#f3f4f6; --card:#ffffff; --ink:#111827; --muted:#4b5563; --blue:#1d4ed8; --green:#15803d; --red:#b91c1c; --amber:#b45309; --border:#e5e7eb; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--ink); }
    header { background: #0f172a; color: #fff; padding: 18px 28px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
    header h1 { margin: 0; font-size: 20px; }
    header p { margin: 2px 0 0; font-size: 13px; color: #cbd5e1; }
    .tabs { display: flex; gap: 8px; }
    .tab-btn { border: 1px solid #475569; background: transparent; color: #e2e8f0; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; }
    .tab-btn.active { background: #2563eb; border-color: #2563eb; color: #fff; }
    main { max-width: 1180px; margin: 22px auto; padding: 0 18px 40px; }
    .panel { display: none; }
    .panel.active { display: block; }
    .card { background: var(--card); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #374151; }
    select, button { font-size: 14px; padding: 8px 10px; border-radius: 6px; border: 1px solid #d1d5db; width: 100%; }
    button.primary { background: var(--blue); color: #fff; border: none; font-weight: 600; cursor: pointer; width: auto; padding: 10px 18px; }
    button.primary:hover { background: #1e40af; }
    .pill { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; margin: 2px 4px 2px 0; }
    .allowed { background: #dcfce7; color: #166534; }
    .approval_required { background: #fef3c7; color: #92400e; }
    .prohibited { background: #fee2e2; color: #991b1b; }
    .ok-box { border-left: 4px solid var(--green); background: #f0fdf4; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
    .warn-box { border-left: 4px solid var(--red); background: #fef2f2; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 10px; border-bottom: 1px solid var(--border); text-align: left; }
    th { background: #f9fafb; }
    .stat-num { font-size: 24px; font-weight: 700; color: var(--blue); }
    .checks { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
    .checks label { display: flex; align-items: center; gap: 6px; font-weight: 500; background: #fffbeb; border: 1px solid #fde68a; padding: 6px 10px; border-radius: 6px; cursor: pointer; }
    .checks input { width: auto; }
    svg { max-width: 100%; height: auto; }
    .muted { color: var(--muted); font-size: 13px; }
    .hint { font-size: 12px; color: var(--muted); margin-top: 4px; }
    .guide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
    .guide-step { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
    .guide-step h4 { margin: 0 0 6px; color: var(--blue); }
    .try-box { background: #eff6ff; border-left: 4px solid var(--blue); padding: 12px 14px; border-radius: 6px; margin-top: 10px; }
    code { background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Secure Agentic AI — Investigation Planner &amp; Evaluation Dashboard</h1>
      <p>Policy-Constrained Search Prototype (Simulation Only · Python Standard Library)</p>
    </div>
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('demo', this)">Live Investigation Demo</button>
      <button class="tab-btn" onclick="switchTab('eval', this)">Evaluation &amp; Charts</button>
      <button class="tab-btn" id="guideTabBtn" onclick="switchTab('guide', this)">How It Works (Guide)</button>
    </div>
  </header>

  <main>
    <section id="tab-demo" class="panel active">
      <div class="card">
        <div class="row">
          <div>
            <label for="scenarioSelect">Security Scenario</label>
            <select id="scenarioSelect" onchange="loadScenarioDetails()"></select>
            <div class="hint">Choose a simulated alert (try <code>LOGIN-APPROVAL-001</code> or <code>cost_tradeoff</code>).</div>
          </div>
          <div>
            <label for="algoSelect">Search Algorithm</label>
            <select id="algoSelect">
              <option value="all">Compare All 4 (BFS, UCS, Greedy, A*)</option>
              <option value="astar">A* Search</option>
              <option value="ucs">Uniform-Cost Search (UCS)</option>
              <option value="greedy">Greedy Best-First</option>
              <option value="bfs">Breadth-First Search (BFS)</option>
            </select>
            <div class="hint">Controls how the planner searches for a safe step-by-step plan.</div>
          </div>
          <div>
            <label for="heurSelect">Heuristic (for Greedy &amp; A*)</label>
            <select id="heurSelect">
              <option value="hmax">h-max (Admissible)</option>
              <option value="zero">h = 0 (Baseline)</option>
            </select>
            <div class="hint">Estimates remaining cost to goal; ignored by BFS and UCS.</div>
          </div>
        </div>

        <div id="scenarioInfo" style="margin-top: 14px;"></div>

        <div style="margin-top: 14px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
          <button class="primary" onclick="runPlanner()">Run Investigation Planner</button>
          <label style="display:flex; align-items:center; gap:6px; margin:0; cursor:pointer;">
            <input type="checkbox" id="baselineCheck" style="width:auto;"> Also run Unconstrained Baseline (shows policy violations)
          </label>
          <span class="muted">New to the controls? Check the <a href="#" onclick="switchTab('guide', document.getElementById('guideTabBtn')); return false;">How It Works (Guide)</a> tab.</span>
        </div>
      </div>

      <div id="plannerOutput"></div>
    </section>

    <section id="tab-eval" class="panel">
      <div class="card" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <h2 style="margin:0 0 4px;">Benchmark Performance &amp; Policy Results</h2>
          <p id="evalSubtitle" class="muted" style="margin:0;">Loading saved evaluation data...</p>
        </div>
        <button class="primary" id="runEvalBtn" onclick="triggerEvaluation()">Re-run Evaluation (10 repeats)</button>
      </div>
      <div id="evalContent"></div>
    </section>

    <section id="tab-guide" class="panel">
      <div class="card">
        <h2 style="margin-top:0;">How to Use the Live Investigation Demo</h2>
        <p class="muted">This prototype simulates how a cybersecurity AI planner picks safe investigation steps when an alert arrives. Nothing connects to real accounts or networks.</p>
        <div class="guide-grid">
          <div class="guide-step">
            <h4>Step 1: Pick a Security Scenario</h4>
            <p>Each scenario represents one simulated security alert (such as a suspicious login, phishing email, or unusual data transfer), a starting clue (<strong>Initial Evidence</strong>), and what needs to be proven (<strong>Required Goal Evidence</strong>).</p>
          </div>
          <div class="guide-step">
            <h4>Step 2: Pick an Algorithm &amp; Heuristic</h4>
            <p>Select one search strategy (<strong>BFS, UCS, Greedy, or A*</strong>) or choose <strong>Compare All 4</strong> to run every algorithm side by side on the exact same alert.</p>
          </div>
          <div class="guide-step">
            <h4>Step 3: Approvals &amp; Baseline (Optional)</h4>
            <p>If a scenario has yellow <strong>approval_required</strong> actions, check their boxes to simulate a human analyst approving them. Check <strong>Unconstrained Baseline</strong> to see what happens without security rules.</p>
          </div>
          <div class="guide-step">
            <h4>Step 4: Run &amp; Compare Results</h4>
            <p>Click <strong>Run Investigation Planner</strong> to generate the step-by-step plan, total cost, search effort metrics, and policy compliance check.</p>
          </div>
        </div>
        <div class="try-box">
          <strong>3 Great Demos to Try Right Away:</strong>
          <ul style="margin:6px 0 0; padding-left:20px;">
            <li><strong>Cost vs. Steps (<code>cost_tradeoff</code> under Test Fixtures):</strong> Choose <em>Compare All 4</em>. BFS &amp; Greedy pick a 1-step expensive route (cost 7), while UCS &amp; A* find a 2-step cheaper route (cost 2).</li>
            <li><strong>Human Approval Gate (<code>LOGIN-APPROVAL-001</code>):</strong> Run once with nothing checked (blocked safely, lists <code>revoke_user_sessions</code> as pending). Then check the approval box and re-run (succeeds safely!).</li>
            <li><strong>Unconstrained Baseline Comparison:</strong> On <code>LOGIN-APPROVAL-001</code> (unchecked), tick <em>Also run Unconstrained Baseline</em> to see the unsafe planner violate policy by taking an unapproved action.</li>
          </ul>
        </div>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">What Changing the Scenario &amp; Policy Colors Mean</h2>
        <p>When you select a scenario, its actions appear as colored pills based on rules in <code>policy_engine.py</code>:</p>
        <p>
          <span class="pill allowed">allowed</span> Read-only investigation steps (checking logs, IP reputation, device status). The planner may include these freely once prerequisites are met.<br>
          <span class="pill approval_required">approval_required</span> High-impact containment steps (resetting passwords, revoking sessions, blocking connections). <strong>Blocked</strong> unless you manually check its approval box.<br>
          <span class="pill prohibited">prohibited</span> Dangerous or illegal actions (deleting logs, wiping devices, exporting confidential data). <strong>Always blocked</strong>—even if someone tries to approve them.
        </p>
        <table>
          <thead><tr><th>Scenario Group</th><th>What Is Inside</th></tr></thead>
          <tbody>
            <tr><td><strong>Core &amp; Approval Validation</strong></td><td>The original suspicious-login example (<code>LOGIN-001</code>) plus 3 scenarios that require human approval before reaching the goal.</td></tr>
            <tr><td><strong>Experimental</strong></td><td>Base templates for Suspicious Login, Phishing Email, and Unusual Data Transfer.</td></tr>
            <tr><td><strong>Benchmark (90)</strong></td><td>90 generated scenarios split evenly across 3 categories and 3 complexities (<em>simple</em>, <em>medium</em>, <em>complex</em>).</td></tr>
            <tr><td><strong>Test Fixtures</strong></td><td>Small focused examples designed to highlight differences between algorithms (<code>cost_tradeoff</code>, <code>approval_gate</code>).</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">What Changing the Search Algorithm Does</h2>
        <table>
          <thead><tr><th>Algorithm</th><th>How It Decides What to Try Next</th><th>Cheapest Cost Guaranteed?</th><th>Best Way to Think About It</th></tr></thead>
          <tbody>
            <tr><td><strong>BFS</strong> (Breadth-First)</td><td>Explores shortest plans by number of steps first (FIFO queue).</td><td>No (ignores action costs)</td><td>Finds the plan with the <strong>fewest steps</strong>, even if a 1-step bundle is expensive.</td></tr>
            <tr><td><strong>UCS</strong> (Uniform-Cost)</td><td>Always expands the path with the lowest cost spent so far: <code>g(n)</code>.</td><td><strong>Yes</strong></td><td>Carefully explores outward by cost. Always optimal, but explores more nodes than A*.</td></tr>
            <tr><td><strong>Greedy Best-First</strong></td><td>Only looks at estimated cost remaining to goal: <code>h(n)</code>.</td><td>No (can get tricked)</td><td>Very fast (expands very few nodes), because it rushes straight toward the goal, sometimes picking a pricier route.</td></tr>
            <tr><td><strong>A* Search</strong></td><td>Combines cost so far + estimated remaining cost: <code>f(n) = g(n) + h(n)</code>.</td><td><strong>Yes</strong> (with <code>h-max</code>)</td><td>Best of both worlds: uses the heuristic to avoid wasted work while still guaranteeing the <strong>cheapest safe plan</strong>.</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">What Changing the Heuristic Does (<code>h-max</code> vs. <code>h = 0</code>)</h2>
        <p>A <strong>heuristic</strong> <code>h(n)</code> is a smart guess of how much cost is still left to finish the investigation. Only <strong>Greedy</strong> and <strong>A*</strong> use it (BFS and UCS ignore this dropdown).</p>
        <ul>
          <li><strong><code>h-max (Admissible)</code>:</strong> Estimates the remaining cost using the most expensive missing piece of evidence (never overestimates the true remaining cost). Because it never overestimates, <strong>A* is guaranteed to find the optimal plan</strong> while expanding fewer nodes than UCS.</li>
          <li><strong><code>h = 0 (Baseline)</code>:</strong> Turns off heuristic guidance (always guesses 0 remaining cost). With <code>h = 0</code>, A* loses its "sense of direction" and behaves identically to UCS (same nodes expanded, same cost), which lets you verify how much work <code>h-max</code> saves.</li>
        </ul>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">How to Read the Results Generated by "Run Investigation Planner"</h2>
        <table>
          <thead><tr><th>Result Field</th><th>Plain-English Meaning</th></tr></thead>
          <tbody>
            <tr><td><strong>Status Banner</strong></td><td><strong style="color:var(--green);">GOAL REACHED (Safe Plan)</strong> means every required piece of evidence can be collected while obeying all security rules. <strong style="color:var(--red);">BLOCKED / GOAL NOT REACHED</strong> means an approval-required step is waiting on human authorization (or no allowed path exists).</td></tr>
            <tr><td><strong>Plan Steps</strong></td><td>The exact ordered list of investigation actions from start to finish (<code>1. check_login_history &rarr; 2. ...</code>).</td></tr>
            <tr><td><strong>Total Cost</strong></td><td>The sum of synthetic costs (analyst effort) for all actions in the plan. Lower is better. Shows <code>N/A</code> if blocked.</td></tr>
            <tr><td><strong>Nodes Expanded</strong></td><td>How many search states the algorithm opened up to inspect next actions. <strong>Lower means smarter, less wasted search work.</strong></td></tr>
            <tr><td><strong>Nodes Generated</strong></td><td>Total candidate next states created during search before filtering out already-visited states.</td></tr>
            <tr><td><strong>Peak Frontier</strong></td><td>The highest number of states waiting in the queue/priority list at one time (measures memory used).</td></tr>
            <tr><td><strong>Time (ms)</strong></td><td>Wall-clock time in milliseconds to run that search (1 ms = 1/1000th of a second).</td></tr>
            <tr><td><strong>Policy Violations</strong></td><td>Always <strong>0</strong> for the secure planner. If you enable <strong>Unconstrained Baseline</strong>, its card shows how many <em>Prohibited</em> or <em>Unapproved</em> actions an unprotected planner would have taken.</td></tr>
            <tr><td><strong>Pending Approvals Needed</strong></td><td>Only shown when blocked: lists the <code>approval_required</code> actions the planner ran into that could unlock progress if a human approves them.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    function switchTab(name, btn) {
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      btn.classList.add('active');
      if (name === 'eval') loadEvaluationResults();
    }

    async function init() {
      const res = await fetch('/api/scenarios');
      const items = await res.json();
      const select = document.getElementById('scenarioSelect');
      const groups = {};
      for (const item of items) {
        if (!groups[item.group]) groups[item.group] = [];
        groups[item.group].push(item);
      }
      for (const [groupName, list] of Object.entries(groups)) {
        const og = document.createElement('optgroup');
        og.label = groupName;
        for (const item of list) {
          const opt = document.createElement('option');
          opt.value = item.path;
          opt.textContent = `${item.scenario_id} (${item.complexity})`;
          og.appendChild(opt);
        }
        select.appendChild(og);
      }
      await loadScenarioDetails();
    }

    async function loadScenarioDetails() {
      const path = document.getElementById('scenarioSelect').value;
      const res = await fetch('/api/scenario?path=' + encodeURIComponent(path));
      const data = await res.json();
      const approvalActions = data.actions.filter(a => a.policy === 'approval_required');
      const approvalHtml = approvalActions.length
        ? `<div style="margin-top:10px;"><label>Simulated Human Approvals (check to authorize):</label><div class="checks">${
            approvalActions.map(a => `<label><input type="checkbox" class="approval-box" value="${a.id}"> ${a.id} (cost ${a.cost})</label>`).join('')
          }</div></div>`
        : '<p class="muted" style="margin-top:8px;">No approval-required actions in this scenario.</p>';

      const actionsHtml = data.actions.map(a =>
        `<span class="pill ${a.policy}">${a.id} (${a.policy}, cost=${a.cost ?? 'N/A'})</span>`
      ).join('');

      document.getElementById('scenarioInfo').innerHTML = `
        <p style="margin:6px 0;"><strong>Description:</strong> ${data.description || 'N/A'}</p>
        <p style="margin:6px 0;"><strong>Initial Evidence:</strong> ${data.initial_evidence.join(', ')}<br>
        <strong>Required Goal Evidence:</strong> ${data.required_evidence.join(', ')}</p>
        <div><strong>Available Actions:</strong><br>${actionsHtml}</div>
        ${approvalHtml}
      `;
    }

    async function runPlanner() {
      const approved = Array.from(document.querySelectorAll('.approval-box:checked')).map(cb => cb.value);
      const body = {
        scenario_path: document.getElementById('scenarioSelect').value,
        algorithm: document.getElementById('algoSelect').value,
        heuristic: document.getElementById('heurSelect').value,
        approved_actions: approved,
        include_baseline: document.getElementById('baselineCheck').checked
      };
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
      const data = await res.json();
      renderPlanResults(data);
    }

    function renderPlanResults(data) {
      let html = '';
      for (const r of data.runs) {
        const ok = r.goal_reached;
        const boxClass = ok ? 'ok-box' : 'warn-box';
        const status = ok ? 'GOAL REACHED (Safe Plan)' : 'BLOCKED / GOAL NOT REACHED';
        const steps = r.actions.length ? r.actions.map((a, i) => `${i + 1}. ${a}`).join(' &rarr; ') : 'None';
        html += `
          <div class="card">
            <div class="${boxClass}">
              <strong>${r.algorithm.toUpperCase()}</strong> ${r.heuristic ? `(${r.heuristic})` : ''} &mdash; <strong>${status}</strong>
            </div>
            <p><strong>Plan Steps:</strong> ${steps}</p>
            <p>
              <strong>Total Cost:</strong> ${r.total_cost ?? 'N/A'} |
              <strong>Nodes Expanded:</strong> ${r.metrics.nodes_expanded} |
              <strong>Nodes Generated:</strong> ${r.metrics.nodes_generated} |
              <strong>Peak Frontier:</strong> ${r.metrics.frontier_peak} |
              <strong>Time:</strong> ${(r.metrics.elapsed_seconds * 1000).toFixed(4)} ms |
              <strong>Policy Violations:</strong> ${r.policy_audit.total_violations}
            </p>
            ${!ok && r.pending_approvals.length ? `<p><strong>Pending Approvals Needed:</strong> ${r.pending_approvals.join(', ')}</p>` : ''}
            ${r.recommendation ? `<p class="muted"><strong>Recommendation:</strong> ${r.recommendation}</p>` : ''}
          </div>
        `;
      }

      if (data.baseline) {
        const b = data.baseline;
        const v = b.policy_audit;
        html += `
          <div class="card">
            <div class="warn-box">
              <strong>UNCONSTRAINED BASELINE (${b.algorithm.toUpperCase()})</strong> &mdash;
              Policy Violations Found: <strong>${v.total_violations}</strong>
              (Prohibited: ${v.prohibited_violations}, Unapproved: ${v.unapproved_violations})
            </div>
            <p><strong>Unsafe Plan Actions:</strong> ${b.actions.join(' &rarr; ') || 'None'}</p>
            <p><strong>Cost:</strong> ${b.total_cost ?? 'N/A'} |
               <strong>Prohibited Used:</strong> ${v.prohibited_actions_used.join(', ') || 'None'} |
               <strong>Unapproved Used:</strong> ${v.unapproved_actions_used.join(', ') || 'None'}</p>
          </div>
        `;
      }
      document.getElementById('plannerOutput').innerHTML = html;
    }

    async function loadEvaluationResults() {
      const res = await fetch('/api/evaluation');
      const data = await res.json();
      const target = document.getElementById('evalContent');
      if (!data.available) {
        document.getElementById('evalSubtitle').textContent = 'No saved results yet. Click "Re-run Evaluation" to generate results and charts.';
        target.innerHTML = '';
        return;
      }

      const totals = data.policy_comparison.totals;
      document.getElementById('evalSubtitle').textContent =
        `Python ${data.environment.python_version} | ${data.optimality.total_scenarios} scenarios | ${data.environment.repeats} timed repeats per run`;

      const tableRows = data.summary_by_config.map(row => `
        <tr>
          <td>${row.label}</td>
          <td>${(data.optimality.optimal_rate[row.config] * 100).toFixed(1)}%</td>
          <td>${row.avg_cost.toFixed(2)}</td>
          <td>${row.avg_plan_length.toFixed(2)}</td>
          <td>${row.avg_nodes_expanded.toFixed(2)}</td>
          <td>${row.avg_nodes_generated.toFixed(2)}</td>
          <td>${row.avg_time_ms.toFixed(4)} ms</td>
          <td>${row.total_policy_violations}</td>
        </tr>
      `).join('');

      const chartsHtml = data.charts.map(c => `<div class="card">${c.svg}</div>`).join('');

      target.innerHTML = `
        <div class="row" style="margin-bottom:16px;">
          <div class="card"><div class="muted">Benchmark Scenarios</div><div class="stat-num">${data.optimality.total_scenarios}</div></div>
          <div class="card"><div class="muted">A* Optimal Matches</div><div class="stat-num">${data.optimality.optimal_matches.astar}/${data.optimality.total_scenarios}</div></div>
          <div class="card"><div class="muted">Secure Policy Violations</div><div class="stat-num" style="color:var(--green);">0</div></div>
          <div class="card"><div class="muted">Unconstrained Violations</div><div class="stat-num" style="color:var(--red);">${totals.unconstrained_approval_violations + totals.unconstrained_shortcut_violations}</div></div>
        </div>
        <div class="card">
          <h3>Overall Algorithm Comparison</h3>
          <table>
            <thead><tr><th>Configuration</th><th>Optimal Rate</th><th>Avg Cost</th><th>Avg Steps</th><th>Avg Expanded</th><th>Avg Generated</th><th>Mean Time</th><th>Violations</th></tr></thead>
            <tbody>${tableRows}</tbody>
          </table>
        </div>
        ${chartsHtml}
      `;
    }

    async function triggerEvaluation() {
      const btn = document.getElementById('runEvalBtn');
      btn.disabled = true;
      btn.textContent = 'Running benchmark...';
      try {
        await fetch('/api/run_evaluation', { method: 'POST' });
        await loadEvaluationResults();
      } finally {
        btn.disabled = false;
        btn.textContent = 'Re-run Evaluation (10 repeats)';
      }
    }

    init();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler serving the HTML page and JSON API."""

    def _send_json(self, data: object, status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, html: str) -> None:
        encoded = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        # Keep terminal output clean unless debugging.
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self._send_html(HTML_PAGE)
            elif parsed.path == "/api/scenarios":
                self._send_json(list_all_scenarios())
            elif parsed.path == "/api/scenario":
                params = parse_qs(parsed.query)
                rel_path = params.get("path", ["scenarios/suspicious_login.json"])[0]
                self._send_json(describe_scenario(rel_path))
            elif parsed.path == "/api/evaluation":
                self._send_json(load_saved_results())
            else:
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except (ValueError, FileNotFoundError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
            if parsed.path == "/api/plan":
                self._send_json(execute_plan_request(body))
            elif parsed.path == "/api/run_evaluation":
                payload = run_evaluation(warmups=1, repeats=10, output_dir=RESULTS_DIR)
                generate_all_visualizations(payload, RESULTS_DIR)
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Create the local HTTP server (used by CLI and automated tests)."""
    return ThreadingHTTPServer((host, port), DashboardHandler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launch the local Secure Agentic AI web dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the web browser")
    args = parser.parse_args(argv)

    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Secure Agentic AI Dashboard running at {url}")
    print("Press Ctrl+C to stop the server.")

    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
