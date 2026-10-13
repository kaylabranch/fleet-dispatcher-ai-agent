# Fleet Dispatch Agent

A simulated fleet-dispatch system where an LLM agent (Google Gemini, via function calling) manages a fleet of
delivery/service robots: assigning tasks, rerouting around disruptions, and explaining its
reasoning. See [.github/copilot-instructions.md](.github/copilot-instructions.md) for the full
design doc.

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
Copy-Item .env.example .env   # then fill in GEMINI_API_KEY
```

Run the API server (starts the tick loop + WebSocket push):

```powershell
uvicorn server.main:app --reload
```

Run the test suite:

```powershell
pytest
```

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

The dashboard expects the API at `ws://localhost:8000/ws` and `http://localhost:8000` (see
`frontend/src/hooks/useFleetSocket.ts`).

Gemini API keys are available through Google AI Studio's free tier, subject to current quota and
model availability. The default model is `gemini-2.5-flash`; override it with `GEMINI_MODEL`.

## Scenarios

Set `SCENARIO` in `.env` to one of the fixtures under `data/scenarios/`:

- `calm_day` — near-zero disruption rate, baseline assignment logic
- `chaos_day` — high disruption rate across all categories
- `deadline_crunch` — multiple tight/expired deadlines, tests escalation
- `sensor_noise` — isolated data-quality issues

## Interaction modes

- **Observer** — dashboard streams fleet state + decision log automatically
- **Intervention** — `POST /intervene` injects a message into the next agent cycle
- **Approval** — costly actions (`recall_to_charge` on an active-task robot, `escalate_task`) are
  held in `pending_approval` until `POST /approvals/{id}` approves/rejects them
- **Query** — `simulate_scenario` tool call, read-only, no world-state mutation

The dashboard also exposes a read-only **What-if query** endpoint at `POST /query`. Gemini usage
and free-tier quotas are controlled by Google and are not unlimited; provider errors are surfaced
instead of silently changing the simulation.
