import { useEffect, useState } from "react";
import type { SimulationStatus } from "./types";

const API_URL = "http://localhost:8000";
const SCENARIOS = ["calm_day", "chaos_day", "deadline_crunch", "sensor_noise"];

interface SimulationControlsProps {
    status: SimulationStatus;
    scenario: string;
}

/** Gives the supervisor explicit control over simulation lifecycle and scenario selection. */
export function SimulationControls({ status, scenario }: SimulationControlsProps) {
    const [selectedScenario, setSelectedScenario] = useState(scenario);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        setSelectedScenario(scenario);
    }, [scenario]);

    async function control(action: "start" | "pause" | "stop" | "reset") {
        setBusy(true);
        setError("");
        const progressLabel = action === "start" ? "Starting" : action === "pause" ? "Pausing" : action === "stop" ? "Stopping" : "Resetting";
        setMessage(`${progressLabel} simulation...`);
        try {
            const response = await fetch(`${API_URL}/simulation`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action,
                    scenario: action === "start" || action === "reset" ? selectedScenario : undefined,
                }),
            });
            if (!response.ok) throw new Error(`Request failed: ${response.status}`);
            const result: { status: SimulationStatus } = await response.json();
            setMessage(
                result.status === "running"
                    ? "Simulation running. The first agent cycle starts now; later cycles follow the configured interval."
                    : `Simulation ${result.status}.`,
            );
        } catch (controlError) {
            setError(controlError instanceof Error ? controlError.message : "Simulation control failed.");
            setMessage("");
        } finally {
            setBusy(false);
        }
    }

    return (
        <section className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                    Scenario
                    <select
                        value={selectedScenario}
                        onChange={(event) => setSelectedScenario(event.target.value)}
                        disabled={status === "running" || busy}
                        className="rounded border border-gray-300 bg-white px-3 py-2"
                    >
                        {SCENARIOS.map((name) => <option key={name} value={name}>{name}</option>)}
                    </select>
                </label>
                <button type="button" onClick={() => void control("start")} disabled={status === "running" || busy} className="rounded bg-green-600 px-4 py-2 text-sm text-white disabled:opacity-50">Start</button>
                <button type="button" onClick={() => void control("pause")} disabled={status !== "running" || busy} className="rounded bg-yellow-600 px-4 py-2 text-sm text-white disabled:opacity-50">Pause</button>
                <button type="button" onClick={() => void control("stop")} disabled={status === "stopped" || busy} className="rounded bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50">Stop</button>
                <button type="button" onClick={() => void control("reset")} disabled={busy} className="rounded bg-gray-700 px-4 py-2 text-sm text-white disabled:opacity-50">Reset</button>
                <span className="text-sm font-semibold uppercase text-gray-700">{busy ? "updating" : status}</span>
            </div>
            <p className="mt-2 text-xs text-gray-600">Start runs one agent cycle every configured interval. Pause holds state; Stop ends automatic cycling; Reset loads the selected scenario from the beginning.</p>
            {message && <p className="mt-2 text-xs text-green-700" aria-live="polite">{message}</p>}
            {error && <p className="mt-2 text-xs text-red-700" role="alert">{error}</p>}
        </section>
    );
}
