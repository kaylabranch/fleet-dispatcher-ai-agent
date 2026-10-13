/**
 * Wire-format types mirroring the FastAPI/Pydantic models exactly (snake_case keys),
 * since no request/response transform layer exists yet — see copilot-instructions.md
 * naming conventions for the intended camelCase mapping if one is added later.
 */

export interface Location {
    x: number;
    y: number;
}

export type RobotStatus = "idle" | "en_route" | "charging" | "broken";

export interface Robot {
    id: string;
    location: Location;
    status: RobotStatus;
    battery: number;
    current_task_id: string | null;
    speed: number;
    last_reported_at: string | null;
}

export type TaskPriority = "low" | "normal" | "high" | "urgent";
export type TaskStatus = "pending" | "assigned" | "in_progress" | "completed" | "failed";

export interface Task {
    id: string;
    pickup: Location;
    dropoff: Location;
    priority: TaskPriority;
    deadline: string | null;
    status: TaskStatus;
    assigned_robot_id: string | null;
}

export type FleetEventType =
    | "breakdown"
    | "low_battery"
    | "blocked_route"
    | "new_urgent_task"
    | "delay"
    | "sensor_anomaly"
    | "deadline_conflict"
    | "intervention_conflict";

export interface FleetEvent {
    id: string;
    type: FleetEventType;
    robot_id: string | null;
    task_id: string | null;
    timestamp: string;
    details: string;
}

export interface Decision {
    action: string;
    robot_id: string | null;
    task_id: string | null;
    reasoning: string;
}

export interface DecisionLogEntry {
    cycle: number;
    timestamp: string;
    decisions: Decision[];
    flagged_risks: string[];
}

export interface FleetSnapshot {
    cycle: number;
    robots: Robot[];
    tasks: Task[];
    recent_events: FleetEvent[];
}

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface PendingApproval {
    id: string;
    action: string;
    payload: Record<string, unknown>;
    reasoning: string;
    created_at: string;
    status: ApprovalStatus;
}

export interface FleetUpdateMessage {
    fleet: FleetSnapshot;
    decision: DecisionLogEntry | null;
    approvals: PendingApproval[];
}
