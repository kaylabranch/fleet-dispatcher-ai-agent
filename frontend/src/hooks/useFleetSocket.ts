import { useEffect, useRef, useState } from "react";
import type { DecisionLogEntry, FleetSnapshot, FleetUpdateMessage, PendingApproval } from "../types";

const WEBSOCKET_URL = "ws://localhost:8000/ws";

/** Connects to the fleet WebSocket and keeps the latest snapshot + decision history in state. */
export function useFleetSocket() {
    const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
    const [decisions, setDecisions] = useState<DecisionLogEntry[]>([]);
    const [approvals, setApprovals] = useState<PendingApproval[]>([]);
    const [connected, setConnected] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        const socket = new WebSocket(WEBSOCKET_URL);
        socketRef.current = socket;

        socket.onopen = () => setConnected(true);
        socket.onclose = () => setConnected(false);
        socket.onmessage = (event) => {
            const message: FleetUpdateMessage = JSON.parse(event.data);
            setFleet(message.fleet);
            setApprovals(message.approvals ?? []);
            if (message.decision) {
                setDecisions((prev) => [...prev, message.decision as DecisionLogEntry]);
            }
        };

        return () => socket.close();
    }, []);

    return { fleet, decisions, approvals, connected };
}
