import { useEffect, useRef, useState } from "react";
import type { DecisionLogEntry, FleetSnapshot, FleetUpdateMessage, PendingApproval, SimulationStatus } from "../types";

const WEBSOCKET_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

/** Connects to the fleet WebSocket and keeps the latest snapshot + decision history in state. */
export function useFleetSocket() {
    const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
    const [decisions, setDecisions] = useState<DecisionLogEntry[]>([]);
    const [approvals, setApprovals] = useState<PendingApproval[]>([]);
    const [connected, setConnected] = useState(false);
    const [connectionError, setConnectionError] = useState("");
    const [runtimeError, setRuntimeError] = useState("");
    const [status, setStatus] = useState<SimulationStatus>("stopped");
    const [scenario, setScenario] = useState("calm_day");
    const socketRef = useRef<WebSocket | null>(null);
    const lastLoggedCycle = useRef<number | null>(null);
    const lastLoggedStatus = useRef<SimulationStatus | null>(null);
    const pollCount = useRef(0);

    useEffect(() => {
        let reconnectTimer: number | undefined;
        let pollTimer: number | undefined;
        let disposed = false;

        async function refreshFromApi() {
            const pollStarted = performance.now();
            pollCount.current += 1;
            try {
                const [fleetResponse, simulationResponse] = await Promise.all([
                    fetch(`${API_URL}/fleet`),
                    fetch(`${API_URL}/simulation`),
                ]);
                if (!fleetResponse.ok || !simulationResponse.ok) throw new Error("Backend request failed.");
                const fleetSnapshot: FleetSnapshot = await fleetResponse.json();
                const simulation: { status: SimulationStatus; scenario: string } = await simulationResponse.json();
                setFleet(fleetSnapshot);
                setStatus(simulation.status);
                setScenario(simulation.scenario);
                const cycleChanged = lastLoggedCycle.current !== fleetSnapshot.cycle;
                const statusChanged = lastLoggedStatus.current !== simulation.status;
                if (cycleChanged || statusChanged || pollCount.current % 5 === 0) {
                    const robots = fleetSnapshot.robots
                        .map((robot) => `${robot.id}=(${robot.location.x.toFixed(1)},${robot.location.y.toFixed(1)})/${robot.status}`)
                        .join(" ");
                    console.info(
                        `[fleet] REST cycle=${fleetSnapshot.cycle} status=${simulation.status} scenario=${simulation.scenario} ` +
                        `changed=${cycleChanged || statusChanged} duration=${Math.round(performance.now() - pollStarted)}ms robots=${robots}`,
                    );
                }
                lastLoggedCycle.current = fleetSnapshot.cycle;
                lastLoggedStatus.current = simulation.status;
                if (!connected) setConnectionError("");
            } catch (error) {
                console.warn(`[fleet] REST poll failed duration=${Math.round(performance.now() - pollStarted)}ms`, error);
                if (!disposed && !connected) {
                    setConnectionError("Backend connection failed. Start the FastAPI server on port 8000.");
                }
            }
        }

        function connect() {
            const socket = new WebSocket(WEBSOCKET_URL);
            socketRef.current = socket;

            socket.onopen = () => {
                console.info(`[fleet] WebSocket connected url=${WEBSOCKET_URL}`);
                setConnected(true);
                setConnectionError("");
            };
            socket.onerror = () => {
                console.error("[fleet] WebSocket error");
                setConnectionError("Backend connection failed. Start the FastAPI server on port 8000.");
            };
            socket.onclose = () => {
                console.warn("[fleet] WebSocket closed; retrying=2s");
                setConnected(false);
                if (!disposed) {
                    reconnectTimer = window.setTimeout(connect, 2000);
                }
            };
            socket.onmessage = (event) => {
                let message: FleetUpdateMessage;
                try {
                    message = JSON.parse(event.data) as FleetUpdateMessage;
                } catch (error) {
                    console.error("[fleet] WebSocket parse failed", error);
                    return;
                }
                console.info(
                    `[fleet] WS cycle=${message.fleet.cycle} status=${message.status} scenario=${message.scenario} ` +
                    `decision=${message.decision !== null} approvals=${message.approvals?.length ?? 0}`,
                );
                setFleet(message.fleet);
                setApprovals(message.approvals ?? []);
                setStatus(message.status);
                setScenario(message.scenario);
                if (message.error) {
                    console.error(`[fleet] BACKEND ERROR cycle=${message.fleet.cycle}: ${message.error}`);
                    setRuntimeError(message.error);
                } else {
                    setRuntimeError("");
                }
                if (message.decision) {
                    setDecisions((prev) => [...prev, message.decision as DecisionLogEntry]);
                }
            };
        }

        connect();
        void refreshFromApi();
        pollTimer = window.setInterval(() => void refreshFromApi(), 1000);

        return () => {
            disposed = true;
            if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
            if (pollTimer !== undefined) window.clearInterval(pollTimer);
            socketRef.current?.close();
        };
    }, []);

    return { fleet, decisions, approvals, connected, status, scenario, connectionError, runtimeError };
}
