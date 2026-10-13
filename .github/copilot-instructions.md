# Fleet Dispatch Agent — Design Doc

## 1. Overview

A simulated fleet-dispatch system where an LLM agent manages a fleet of delivery/service robots: assigning tasks, rerouting around disruptions, and explaining its reasoning. No real hardware — the "world" is a mock simulator (grid + task queue + random events) that the agent observes and acts on through a small set of tools.

**Goals**
- Demonstrate agentic reasoning over a stateful system (observe → decide → act → update)
- Show transparent, explainable decisions (not a black box)
- Support human-in-the-loop supervision: observe, intervene, approve, query
- Exercise the agent under realistic non-happy-path conditions (delays, failures, conflicts), not just clean assignment logic
- Be small enough to build in stages and demo live

**Non-goals (v1)**
- Real mapping/routing algorithms (use straight-line/grid distance, not real road networks)
- Multi-tenant or persistence-heavy backend (SQLite or JSON file is enough)
- Production auth/security — this is a demo project

---

## 2. Tech Stack (Python)

| Layer | Choice | Why |
|---|---|---|
| Runtime | Python 3.11+ | Also doubles as practice toward the PCPP1 cert |
| Agent LLM | Google Gemini (Google Gen AI Python SDK, function calling) | Free-tier-friendly function calling with structured tool inputs |
| Simulator | Plain Python module, Pydantic models | Pydantic gives schema validation for free, including on agent tool-call inputs |
| Persistence | SQLite (`sqlite3` or `sqlmodel`) or JSON file | Enough for task/decision history at this scale |
| API layer | FastAPI | Async, native WebSocket support, auto-generated `/docs` from the same Pydantic models |
| Frontend | React + Vite + Tailwind | Frontend stays JS/TS regardless of backend language choice |
| Real-time push | FastAPI WebSocket endpoint | Pushes fleet state + agent decisions to the dashboard live |
| Testing | pytest | Standard Python testing |
| Data validation | Pydantic v2 | Replaces TS interfaces; validates agent tool-call payloads at runtime, catching hallucinated fields/types before they hit the simulator |

---

## 3. Data Model (with example fake data)

### Robot

```python
from pydantic import BaseModel
from typing import Literal, Optional

class Location(BaseModel):
    x: float
    y: float

class Robot(BaseModel):
    id: str
    location: Location
    status: Literal["idle", "en_route", "charging", "broken"]
    battery: float  # 0-100
    current_task_id: Optional[str] = None
    speed: float  # grid units per tick
    last_reported_at: Optional[str] = None  # ISO timestamp; used to detect stale/phantom readings
```

```json
[
  { "id": "r1", "location": { "x": 2, "y": 5 }, "status": "idle", "battery": 92, "current_task_id": null, "speed": 1, "last_reported_at": "2026-09-21T18:00:00Z" },
  { "id": "r2", "location": { "x": 8, "y": 1 }, "status": "en_route", "battery": 61, "current_task_id": "t12", "speed": 1, "last_reported_at": "2026-09-21T18:00:00Z" },
  { "id": "r3", "location": { "x": 4, "y": 4 }, "status": "idle", "battery": 14, "current_task_id": null, "speed": 1, "last_reported_at": "2026-09-21T18:00:00Z" },
  { "id": "r4", "location": { "x": 0, "y": 0 }, "status": "broken", "battery": 40, "current_task_id": null, "speed": 0, "last_reported_at": "2026-09-21T17:58:00Z" }
]
```

### Task

```python
class Task(BaseModel):
    id: str
    pickup: Location
    dropoff: Location
    priority: Literal["low", "normal", "high", "urgent"]
    deadline: Optional[str] = None  # ISO timestamp; nullable to test missing-data handling
    status: Literal["pending", "assigned", "in_progress", "completed", "failed"]
    assigned_robot_id: Optional[str] = None
```

```json
[
  { "id": "t12", "pickup": { "x": 8, "y": 1 }, "dropoff": { "x": 9, "y": 6 }, "priority": "normal", "deadline": "2026-09-22T14:30:00Z", "status": "in_progress", "assigned_robot_id": "r2" },
  { "id": "t13", "pickup": { "x": 1, "y": 1 }, "dropoff": { "x": 6, "y": 9 }, "priority": "urgent", "deadline": "2026-09-21T21:00:00Z", "status": "pending", "assigned_robot_id": null },
  { "id": "t14", "pickup": { "x": 3, "y": 3 }, "dropoff": { "x": 5, "y": 5 }, "priority": "high", "deadline": "2026-09-21T17:00:00Z", "status": "pending", "assigned_robot_id": null }
]
```
`t14`'s deadline is already in the past relative to the simulated clock — a fixture for testing the `escalate_task` path on arrival.

### Event (disruption)

```python
class FleetEvent(BaseModel):
    id: str
    type: Literal[
        "breakdown", "low_battery", "blocked_route", "new_urgent_task",
        "delay", "sensor_anomaly", "deadline_conflict", "intervention_conflict"
    ]
    robot_id: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: str
    details: str
```

```json
[
  { "id": "e5", "type": "breakdown", "robot_id": "r4", "timestamp": "2026-09-21T18:02:00Z", "details": "r4 stalled at (0,0) while idle, motor fault" },
  { "id": "e6", "type": "breakdown", "robot_id": "r2", "task_id": "t12", "timestamp": "2026-09-21T18:05:00Z", "details": "r2 stalled mid-route on t12, motor fault — task now unassigned mid-flight" },
  { "id": "e7", "type": "delay", "robot_id": "r2", "task_id": "t12", "timestamp": "2026-09-21T18:03:00Z", "details": "r2 moving at 0.4x expected speed, obstacle on route; ETA slipping past deadline" },
  { "id": "e8", "type": "low_battery", "robot_id": "r2", "task_id": "t12", "timestamp": "2026-09-21T18:06:00Z", "details": "r2 battery dropped to 9% mid-route — must decide: push through, abandon, or reroute a second robot to finish t12" },
  { "id": "e9", "type": "sensor_anomaly", "robot_id": "r3", "timestamp": "2026-09-21T18:07:00Z", "details": "r3 reported location (40,40), inconsistent with last known position (4,4) and max possible travel — likely bad reading, do not trust blindly" },
  { "id": "e10", "type": "new_urgent_task", "task_id": "t15", "timestamp": "2026-09-21T18:08:00Z", "details": "second urgent task appeared with only one idle, sufficiently-charged robot available — forces a prioritization tradeoff between t13 and t15" },
  { "id": "e11", "type": "intervention_conflict", "robot_id": "r5", "timestamp": "2026-09-21T18:09:00Z", "details": "user said 'don't use r5 today' while agent was mid-assignment of r5 to a task — tests intervention handling under contention" }
]
```

### Decision log entry (agent output)

```json
{
  "cycle": 42,
  "timestamp": "2026-09-21T18:02:15Z",
  "decisions": [
    {
      "action": "assign_task",
      "robot_id": "r1",
      "task_id": "t13",
      "reasoning": "r1 is idle, closest to pickup (distance 6.4), battery sufficient for round trip; r3 excluded due to low battery (14%)"
    },
    {
      "action": "recall_to_charge",
      "robot_id": "r3",
      "reasoning": "battery below 20% threshold, no active task"
    }
  ],
  "flagged_risks": [
    "r4 broken at (0,0) — no task currently assigned, but blocks that grid cell",
    "t14 deadline already passed on arrival — recommend escalation, not auto-assignment"
  ]
}
```

---

## 4. Non-Happy-Path Scenarios (design rationale)

Static, clean data only exercises assignment logic. The scenarios below exercise reasoning-under-pressure, replanning, and risk-flagging — the actual point of the demo.

| Category | Scenario | What it tests |
|---|---|---|
| Delay | Robot moving slower than estimated | Does the agent notice a deadline trending toward miss *before* it fails? |
| Delay | Task deadline already past at assignment time | Does it route to `escalate_task` instead of auto-assigning? |
| Failure | Breakdown while idle | Low-urgency handling |
| Failure | Breakdown mid-route with active task | Forces reassignment logic |
| Failure | Battery dies mid-route (not just at idle) | Harder tradeoff: abandon vs. push through vs. send a second robot to finish |
| Data quality | Sensor anomaly / inconsistent location report | Does the agent (or simulator) sanity-check inputs instead of trusting them blindly? |
| Data quality | Missing/null deadline field | Does Pydantic validation and the prompt handle incomplete data gracefully instead of crashing? |
| Conflict | Two urgent tasks, one available robot | Prioritization tradeoff, inspectable in the reasoning trace |
| Conflict | User intervention conflicts with an in-flight agent decision | Tests intervention-mode plumbing under contention |

**Implementation approach:** keep the event generator (`events.py`) parameterized with per-category probabilities rather than one fixed script, so you can dial chaos up for a demo or down to near-zero when verifying basic logic.

**Suggested scenario fixtures** (named JSON files under `data/scenarios/`):
- `calm_day.json` — near-zero disruption rate, verifies baseline assignment logic
- `chaos_day.json` — high disruption rate across all categories, good for a live reasoning demo
- `deadline_crunch.json` — multiple tasks with tight/expired deadlines, tests escalation and prioritization specifically
- `sensor_noise.json` — isolated data-quality issues, tests input validation without other disruptions muddying the signal

---

## 5. Agent Loop

```
every tick (e.g. every 5s of sim time, or on event/user input):
  1. Snapshot: serialize robots + tasks + recent events (last ~10)
  2. Build prompt: system instructions + tool definitions + snapshot + any pending user message
  3. Call Gemini with function calling enabled
  4. Execute returned tool calls against the simulator
  5. Simulator advances world state (movement, battery drain, task completion)
  6. Append decision + reasoning to the log
  7. Push updated state to frontend via WebSocket
```

Keep the reasoning field **mandatory** on every tool call — enforce via the tool schema description ("always include a `reasoning` string explaining why").

---

## 6. Tools Exposed to the Agent

| Tool | Signature | Notes |
|---|---|---|
| `get_fleet_status` | `() -> {robots, tasks, events}` | Read-only; agent can call mid-cycle to refresh understanding |
| `assign_task` | `(robot_id, task_id, reasoning) -> None` | Only valid on idle robots |
| `reroute_robot` | `(robot_id, new_path, reasoning) -> None` | Overrides current path |
| `recall_to_charge` | `(robot_id, reasoning) -> None` | Sends robot to nearest charging node |
| `escalate_task` | `(task_id, reason) -> None` | For tasks that can't be fulfilled in time — surfaces to human |
| `simulate_scenario` | `(hypothetical_change) -> outcome_summary` | Runs planning logic without committing — powers "what if" queries |

All tool inputs are Pydantic models, so malformed or hallucinated agent output is rejected before it reaches the simulator, rather than causing a silent bad state change.

---

## 7. Interaction Modes

| Mode | User action | System behavior |
|---|---|---|
| **Observer** | none | Dashboard streams fleet state + decision log in real time |
| **Intervention** | types a command ("recall r3 now") | Message injected into next cycle's prompt; agent replans incorporating it |
| **Approval** | agent proposes a costly/irreversible action | Action held in `pending_approval` state; UI shows Approve/Reject/Modify; only applied on approval |
| **Query** | asks a question ("why did you route r2 that way?" / "what if r1 went offline?") | Routed to a read-only or `simulate_scenario` call; no world-state mutation |

Approval-gated actions (v1 suggestion): `recall_to_charge` on a robot with an active task, and `escalate_task`.

---

## 8. Project Structure

```
fleet-agent/
  simulator/
    world.py            # grid, robots, tasks, tick logic
    events.py            # disruption generator (parameterized by category probability)
    models.py             # Pydantic models
  agent/
    tools.py              # tool schemas + handlers
    loop.py                # the observe-decide-act-update cycle
    prompt.py             # system prompt + snapshot serialization
  server/
    main.py                # FastAPI app + WebSocket endpoint
    routes.py              # REST endpoints (manual overrides, history)
  data/
    scenarios/
      calm_day.json
      chaos_day.json
      deadline_crunch.json
      sensor_noise.json
    fleet.sqlite            # or fleet-state.json
  frontend/
    src/
      Dashboard.tsx
      FleetGrid.tsx
      DecisionLog.tsx
      ChatInput.tsx
```

---

## 9. Build Order

1. **Static simulator** — hardcoded robots/tasks, no agent yet; verify tick/movement/battery logic
2. **One-shot agent call** — feed a snapshot to Gemini, get back function calls, apply manually (no loop)
3. **Loop it** — automate the tick cycle, add logging
4. **Add non-happy-path events** — start with `calm_day`, layer in `chaos_day` categories one at a time
5. **Add reasoning trace output** — structured decisions + risks as shown above
6. **Dashboard** — grid visualization + decision log, read-only first
7. **Intervention** — chat input that injects into next cycle
8. **Approval mode** — gate costly actions
9. **Query/what-if** — `simulate_scenario` tool, no-commit planning

Steps 1–5 are a working CLI demo; 6–9 turn it into something you'd show live in an interview.

---

## 10. Open Questions / Decisions to Make Later

- How much history to include in each prompt (full log vs. last N cycles vs. summarized)?
- Whether to add a periodic "reflection" step where the agent reviews its own past decisions and outcomes
- Whether battery/distance math should be real-world-ish (kWh, meters) or abstract grid units — abstract is fine for a demo, real units read better in an interview
- Exact probability weights for each disruption category in `events.py` — start conservative, tune after seeing how the agent behaves

# General coding guidelines — Fleet Dispatch Agent

## Principles
- Simplicity: Write code that is easy to read, understand, and maintain. Avoid unnecessary complexity and strive for clarity in your code.
- Modularity: Organize your code into small, reusable modules that encapsulate specific functionality.
- Single Responsibility: Each module, class, or function should have a single responsibility or purpose. Avoid mixing unrelated functionality in the same code unit.
- Consistency: Follow consistent coding conventions and best practices throughout the codebase. This includes naming conventions, formatting, and code structure.
- Readability: Prioritize code readability over cleverness. Write code that is easy to follow and understand, even for someone who is not familiar with the codebase.
- Modern Practices: Use modern language features and best practices to write clean, efficient, and maintainable code. Avoid outdated or deprecated patterns and libraries.

## Language and framework
- Backend: Python 3.11+, FastAPI, Pydantic v2. Use the latest stable versions of these technologies.
- Frontend: TypeScript, React + Vite, Tailwind. Use the latest stable versions of these technologies.
- Use type hints on all Python function signatures — no untyped `def` in application code.
- Use Pydantic models (not raw `dict`s) for all data crossing a function, tool, or API boundary — request/response bodies, tool-call inputs, simulator state.
- Prefer `async def` for all FastAPI route handlers and any I/O-bound function (LLM calls, DB access, WebSocket sends).
- Follow the coding conventions and best practices of each language/framework being used — PEP 8 for Python, standard React/TS conventions for the frontend.
- Use consistent naming conventions for variables, functions, classes, and other identifiers within each language (see below — conventions differ between the Python backend and TS frontend).

## Documentation
- The README and `.github/copilot-instructions.md` files should be updated as features are added or modified, providing clear instructions on how to run the simulation, start the agent loop, and use any new functionality.
- Every Pydantic model and public function should have a docstring describing its purpose, not just its parameters.
- Every tool exposed to the agent (`assign_task`, `reroute_robot`, etc.) must have a clear, complete docstring/description, since this text is what the LLM uses to decide when and how to call it — treat these as user-facing documentation, not internal comments.

## Naming conventions
- Use descriptive and meaningful names for variables, functions, classes, and other identifiers.
- Avoid using abbreviations or single-letter names unless they are widely accepted and understood in the context of the codebase (e.g. `x`/`y` for grid coordinates is fine).
- **Python (backend, simulator, agent):** `snake_case` for variables and functions, `PascalCase` for classes and Pydantic models, `UPPER_CASE` for constants — per PEP 8.
- **TypeScript (frontend):** `camelCase` for variables and functions, `PascalCase` for classes and components, `UPPER_CASE` for constants.
- Keep field names consistent across the Python/Pydantic models and any TS types the frontend defines for the same data (e.g. `robot_id` in Python API payloads maps predictably to `robotId` in the frontend, not a differently-named field).

## Code reuse and utilities
- Prefer using existing functions if they exist, rather than writing new ones.
- Avoid duplicating code. If you find yourself writing the same code in multiple places, consider refactoring it into a shared utility module (e.g. `simulator/utils.py` for grid/distance math used by both the simulator and the agent's tools).
- When creating utility functions, ensure they are well-documented (docstrings) and tested.
- Use descriptive names for utility functions that clearly indicate their purpose and behavior.
- Pay attention to other files in the provided context to avoid duplicating existing functionality — in particular, check `simulator/models.py` before defining a new Pydantic model, and `agent/tools.py` before adding a new tool. Reuse or extend an existing model/tool rather than creating a near-duplicate. Can modify if modifications would not change existing behavior.

## Testing
- Write unit tests for all new features and bug fixes, using **pytest** for the Python backend and **Vitest** for the frontend.
- Ensure that tests cover edge cases and non-happy-path scenarios in particular — this project's whole point is agent behavior under disruption, so tests should include breakdowns, delays, low battery, conflicting priorities, and malformed/missing data, not just clean assignment paths.
- Use a consistent testing framework per side of the stack and follow its best practices — pytest fixtures for simulator/agent state, React Testing Library conventions for any component tests.
- When writing tests, aim for clarity and maintainability. Tests should be easy to read and understand, even for someone unfamiliar with the codebase.
- When modifying existing code, update or add tests as necessary to ensure that the changes do not introduce regressions.
- Agent tool handlers should be tested independently of the LLM call itself — mock the tool-call payload (a valid Pydantic instance) and assert on simulator state changes, rather than requiring a live API call in every test.