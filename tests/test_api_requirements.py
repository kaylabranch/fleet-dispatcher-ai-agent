"""Executable API requirements for browser-based human supervision."""

from __future__ import annotations

from fastapi.testclient import TestClient

from server.main import app


def test_browser_interventions_are_allowed_from_the_vite_dev_server() -> None:
    """The dashboard must be able to POST JSON interventions from localhost:5173."""
    with TestClient(app) as client:
        response = client.options(
            "/intervene",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_approving_an_action_applies_it_and_clears_the_approval() -> None:
    """Approve/reject must mutate state, drop the approval, and report unknown IDs as 404."""
    from agent.client import ToolCall
    from server.state import get_app_state

    with TestClient(app) as client:
        state = get_app_state()
        state.reset_simulation("chaos_day")
        state.loop._apply_tool_call(
            ToolCall(id="a1", name="recall_to_charge", input={"robot_id": "r1", "reasoning": "low battery"})
        )
        state.loop._apply_tool_call(
            ToolCall(id="a2", name="escalate_task", input={"task_id": "t14", "reasoning": "deadline passed"})
        )

        approved = client.post("/approvals/a1", json={"action": "approve"})
        rejected = client.post("/approvals/a2", json={"action": "reject"})
        missing = client.post("/approvals/a1", json={"action": "approve"})

        assert approved.status_code == 200
        assert rejected.status_code == 200
        assert missing.status_code == 404
        assert state.loop.world.robots["r1"].status == "charging"
        assert state.loop.pending_approvals == {}
        outcomes = [entry.decisions[0].reasoning for entry in state.loop.decision_log[-2:]]
        assert outcomes[0].startswith("[approved]")
        assert outcomes[1].startswith("[rejected]")
