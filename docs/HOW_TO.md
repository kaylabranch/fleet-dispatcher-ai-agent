# Fleet Dispatch Agent: How-To Guide

This guide explains how to run the simulator, operate the dashboard, and supervise Gemini's decisions.

> **Scope:** This is a simulated fleet-dispatch demo. It does not control physical robots and is not a production safety or regulatory system.

## 1. Prerequisites

Install or have available:

- Python 3.11 or newer
- Node.js and npm
- A Google Gemini API key from Google AI Studio
- PowerShell on Windows, or equivalent shell commands on another platform

The Gemini free tier is subject to current Google quota and model availability. It is not unlimited.

## 2. Install the backend

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

If PowerShell blocks activation, run the commands through the virtual-environment interpreter instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 3. Configure Gemini and the simulator

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
TICK_INTERVAL_SECONDS=5
```

### Scenario choices

- `calm_day` — baseline assignment behavior with few disruptions
- `chaos_day` — multiple breakdown, delay, battery, and conflict events
- `deadline_crunch` — expired and tight deadlines requiring prioritization/escalation
- `sensor_noise` — anomalous robot readings and trust checks

The simulation starts stopped. Select the scenario in the dashboard before clicking **Start**;
you can change scenarios without editing `.env` or restarting the backend.

## 4. Start the backend

Open a terminal at the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn server.main:app --reload
```

The API runs at `http://localhost:8000`.

Useful checks:

- Fleet state: `http://localhost:8000/fleet`
- Decision history: `http://localhost:8000/decisions`
- Pending approvals: `http://localhost:8000/approvals`
- Interactive API documentation: `http://localhost:8000/docs`

The backend waits for the dashboard's **Start** command, then runs an agent cycle every
`TICK_INTERVAL_SECONDS` seconds. Each cycle generates configured events, sends a snapshot to
Gemini, validates returned function calls, applies permitted actions, advances the simulator, and
broadcasts the result over WebSocket.

## 5. Start the dashboard

Open a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

The dashboard connects automatically to these internal backend addresses:

- WebSocket: `ws://localhost:8000/ws`
- REST API: `http://localhost:8000`

Users normally do not open those addresses directly. Open the Vite dashboard at
`http://localhost:5173`; the browser uses the REST API and WebSocket behind the scenes.

The dashboard displays lifecycle controls, scenario selection, fleet grid, pending tasks, decision
reasoning, flagged risks, approval requests, intervention input, and what-if query controls.

## 6. Understand the autonomy midpoint

The default policy is **hands-off for routine work, human review for exceptions**.

### Actions Gemini can perform automatically

- Assign a valid idle robot to a pending task
- Reroute a robot with a validated path
- Request fleet status
- Run a read-only simulation

The simulator still rejects invalid or unsafe state changes, including assignments to broken, unavailable, sensor-untrusted, or undercharged robots.

### Actions that require approval

These actions are held in the approval queue:

- `recall_to_charge`
- `escalate_task`

A supervisor can:

1. **Approve** — apply the proposed action unchanged.
2. **Reject** — discard the proposal.
3. **Modify & apply** — edit the JSON payload, then apply it through the same Pydantic validation and simulator handler used by Gemini.

Modification changes the action parameters, but it does not bypass simulator safety rules.

## 7. Run the simulation from the dashboard

The dashboard is the operator's starting point:

1. Open `http://localhost:5173`.
2. Choose `calm_day`, `chaos_day`, `deadline_crunch`, or `sensor_noise` in the **Scenario** selector.
3. Click **Start**. The status changes to `running` and cycles begin automatically.
4. Click **Pause** to hold the current world state while reviewing decisions or approvals.
5. Click **Start** again to resume a paused simulation.
6. Click **Stop** to stop automatic cycles without changing the current state.
7. Click **Reset** to load the selected scenario from cycle zero.

The cycle number, fleet grid, events, decisions, and pending approvals update as the simulation
runs. Use **Intervene** while running or paused to queue a human instruction for the next cycle.

## 8. Use an intervention

Use the **Intervene** box when something unusual needs human direction, for example:

- `Do not use r5 today.`
- `Prioritize the urgent task over normal deliveries.`
- `Recall r3 if its battery falls below 20 percent.`

Click **Send**. The message is queued and included in the next agent cycle. It does not directly mutate the world; Gemini evaluates it alongside the current snapshot.

You can also send an intervention with PowerShell:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8000/intervene `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Do not use r5 today."}'
```

## 9. Review and modify an approval

When Gemini proposes a gated action:

1. Open **Pending approvals** in the dashboard.
2. Read the action and Gemini's reasoning.
3. Review the JSON payload in the editor.
4. Choose **Approve**, **Reject**, or **Modify & apply**.
5. Confirm the fleet grid and decision log reflect the result.

For API clients, use:

```powershell
# Approve
Invoke-RestMethod `
  -Uri http://localhost:8000/approvals/APPROVAL_ID `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"action":"approve"}'

# Reject
Invoke-RestMethod `
  -Uri http://localhost:8000/approvals/APPROVAL_ID `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"action":"reject"}'

# Modify and apply
Invoke-RestMethod `
  -Uri http://localhost:8000/approvals/APPROVAL_ID `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"action":"modify","payload":{"robot_id":"r1","reasoning":"Supervisor confirmed this action."}}'
```

Replace `APPROVAL_ID` with the ID returned by `GET /approvals` or shown by the dashboard.

## 10. Ask a what-if question

The **What-if query** control is read-only. Example questions include:

- `What if r1 went offline?`
- `How many idle robots are available?`
- `What capacity remains for pending tasks?`

The current endpoint returns a simulator capacity summary and does not change robots, tasks, events, or approvals:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8000/query `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"hypothetical_change":"What if r1 went offline?"}'
```

## 11. Recommended demo flow

1. Start with `SCENARIO=calm_day` and confirm the dashboard connects.
2. Show an automatic assignment and its reasoning.
3. Change to `SCENARIO=deadline_crunch` and restart the backend.
4. Demonstrate an escalation appearing in **Pending approvals**.
5. Reject it or modify its reasoning/payload, then verify the result.
6. Send an intervention such as `Prioritize urgent work.`
7. Use a what-if query to show that planning does not mutate the fleet.
8. Finish with `SCENARIO=chaos_day` to demonstrate flagged risks and failure handling.

## 12. Troubleshooting

### `GEMINI_API_KEY must be set`

Make sure `.env` exists in the repository root and contains `GEMINI_API_KEY`. Restart Uvicorn after changing it.

### The dashboard says disconnected

Confirm that:

1. Uvicorn is running on port 8000.
2. The dashboard is running on port 5173.
3. The browser console has no WebSocket errors.
4. The backend responds at `http://localhost:8000/fleet`.

### CORS or intervention errors

Use the Vite origin shown in the browser, normally `http://localhost:5173`. The backend allows localhost and 127.0.0.1 on port 5173.

### No decisions appear

Check the Uvicorn terminal for Gemini API or quota errors. The simulator still streams an initial fleet snapshot when the dashboard connects, but decisions require a successful agent cycle.

### A scenario change had no effect

Stop and restart Uvicorn after changing `SCENARIO`; scenarios load at application startup.

## 13. Run tests

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run that command from the repository root. It intentionally uses the virtual-environment
interpreter so it works even when PowerShell has not activated `.venv`; a bare `pytest` command
is not available unless `.venv\Scripts` is on `PATH`.

The project filters two known deprecation warnings emitted inside third-party Starlette and Google
Gen AI SDK modules while leaving project warnings visible.

Frontend:

```powershell
Set-Location frontend
npm test -- --run
npm run build
```
