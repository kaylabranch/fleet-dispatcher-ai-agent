import { useEffect, useRef, useState } from "react";
import type { DecisionLogEntry, FleetSnapshot, FleetUpdateMessage, PendingApproval, SimulationStatus } from "../types";

const WEBSOCKET_URL = "ws://localhost:8000/ws";

/** Connects to the fleet WebSocket and keeps the latest snapshot + decision history in state. */
export function useFleetSocket() {
    const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
    const [decisions, setDecisions] = useState<DecisionLogEntry[]>([]);
    const [approvals, setApprovals] = useState<PendingApproval[]>([]);
    const [connected, setConnected] = useState(false);
    const [connectionError, setConnectionError] = useState("");
    const [status, setStatus] = useState<SimulationStatus>("stopped");
    const [scenario, setScenario] = useState("calm_day");
    const socketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        let reconnectTimer: number | undefined;
        let disposed = false;

        function connect() {
            const socket = new WebSocket(WEBSOCKET_URL);
            socketRef.current = socket;

            socket.onopen = () => {
                setConnected(true);
                setConnectionError("");
            };
            socket.onerror = () => {
                setConnectionError("Backend connection failed. Start the FastAPI server on port 8000.");
            };
            socket.onclose = () => {
                setConnected(false);
                if (!disposed) {
                    reconnectTimer = window.setTimeout(connect, 2000);
                }
            };
            socket.onmessage = (event) => {
                const message: FleetUpdateMessage = JSON.parse(event.data);
                setFleet(message.fleet);
                setApprovals(message.approvals ?? []);
                setStatus(message.status);
                setScenario(message.scenario);
                if (message.decision) {
                    setDecisions((prev) => [...prev, message.decision as DecisionLogEntry]);
                }
            };
        }

        connect();

        return () => {
            disposed = true;
            if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
            socketRef.current?.close();
        };
    }, []);

    return { fleet, decisions, approvals, connected, status, scenario, connectionError };
}
