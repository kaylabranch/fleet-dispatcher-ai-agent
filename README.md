# Fleet Dispatch Agent

[WIP] A simulated fleet-dispatch system where an LLM agent (Google Gemini, via function calling) manages a fleet of
delivery/service robots: assigning tasks, rerouting around disruptions, and explaining its
reasoning. See [.github/copilot-instructions.md](.github/copilot-instructions.md) for the full
design doc.

## How-to guide

For a complete step-by-step operator guide, see [docs/HOW_TO.md](docs/HOW_TO.md). It covers Gemini setup, scenario selection, starting the backend and dashboard, interventions, approvals, modified actions, what-if queries, troubleshooting, and validation.

## Project layout

```
simulator/   # grid world, robots, tasks, disruption events (Pydantic models)
agent/       # tool schemas/handlers, prompt building, Gemini client, the observe-decide-act loop
server/      # FastAPI app, WebSocket push, REST routes for intervention/approval
data/        # scenario fixtures + runtime state
tests/       # pytest suite for simulator/agent/server
frontend/    # React + Vite + Tailwind dashboard
```

## Backend setup

```powershell
# from repo root
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

In the new .env file, add your Gemini API key.
Run the API server (starts the tick loop + WebSocket push):

```powershell
uvicorn server.main:app --reload
```

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Use the virtual-environment interpreter explicitly when running from the repository root. A bare
`pytest` command only works after `.venv\Scripts` has been added to the current PowerShell `PATH`
by activating the environment with `.venv\Scripts\Activate.ps1`.

The test configuration also filters two known deprecation warnings emitted inside third-party
Starlette and Google Gen AI SDK modules; warnings from project code are not filtered.

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open the dashboard at the Vite URL, normally `http://localhost:5173`.

Gemini API keys are available through Google AI Studio's free tier, subject to current quota and
model availability. The default model is `gemini-3.8-flash`; override it with `GEMINI_MODEL`.
Set `GEMINI_TIMEOUT_SECONDS` to bound provider calls (default: 5 seconds), and `GEMINI_MIN_REQUEST_INTERVAL_SECONDS` to space calls (default: 1 second). Each cycle allows at most three agent turns, including follow-ups. `TICK_INTERVAL_SECONDS` defaults to 2 seconds for a responsive demo. Provider retries are disabled, so a timeout or transient provider failure is logged and the simulator still advances instead of blocking indefinitely.
Robot movement advances at the beginning of a cycle, before the Gemini request, so a slow provider cannot freeze the map.
If Gemini fails once during a run, the backend opens a circuit breaker and uses local fallback dispatch for subsequent cycles until Reset; this prevents repeated provider failures from stalling the simulation.

## Scenarios

Select the scenario from the dashboard before starting the simulation:

- `calm_day` — near-zero disruption rate, baseline assignment logic
- `chaos_day` — high disruption rate across all categories
- `deadline_crunch` — multiple tight/expired deadlines, tests escalation
- `sensor_noise` — isolated data-quality issues

The backend starts stopped. Open the dashboard, select a scenario, and click **Start**.

## Interaction modes

- **Observer** — dashboard streams fleet state + decision log automatically
- **Intervention** — `POST /intervene` injects a message into the next agent cycle
- **Approval** — costly actions (`recall_to_charge` on an active-task robot, `escalate_task`) are
  held in `pending_approval` until `POST /approvals/{id}` approves, rejects, or modifies them
- **Query** — `simulate_scenario` tool call, read-only, no world-state mutation

The dashboard also exposes a read-only **What-if query** endpoint at `POST /query`. Gemini usage
and free-tier quotas are controlled by Google and are not unlimited; provider errors are surfaced
instead of silently changing the simulation.

## Human-in-the-loop midpoint

The system is intentionally **hands-off by default with exception-based supervision**:

- Low-risk actions such as normal task assignment, rerouting, status checks, and read-only
  simulations proceed automatically after Pydantic and simulator validation.
- Higher-impact actions such as recalling a robot or escalating a task pause in
  `pending_approval` until a supervisor reviews them.
- A supervisor can **approve**, **reject**, or **modify and apply** a pending action. Modification
  uses the same Pydantic model and simulator handler as an autonomous action, so human overrides
  cannot bypass safety validation.
- Interventions remain available for unusual situations without requiring a human to monitor every
  cycle.

This balances autonomy and control: requiring approval for every assignment would make the demo
slow and operationally unrealistic, while allowing irreversible or disruptive actions without
review would reduce accountability. The tradeoff is that supervisors still need to monitor the
approval queue and decide how conservative the approval policy should be for a real deployment.
This repository is a simulator and does not claim to satisfy regulations or safety requirements
for physical robots.
