/** Plain-language labels shared by the approval panel and the decision log. */

const ACTION_LABELS: Record<string, string> = {
    assign_task: "Assign task",
    reroute_robot: "Reroute robot",
    recall_to_charge: "Send to charge",
    escalate_task: "Escalate task",
    simulate_scenario: "Run what-if",
};

/** Prefixes the backend adds to reasoning text; they are shown as badges instead. */
const REASONING_PREFIX = /^\s*(\[pending approval\]|\[local fallback\]|\[approved(?: \(modified\))?\]|\[rejected\])\s*/gi;

export type ApprovalOutcome = "approved" | "approved (modified)" | "rejected";

/** Returns how a supervisor resolved the action, if the reasoning carries an outcome marker. */
export function approvalOutcome(reasoning: string): ApprovalOutcome | null {
    const match = reasoning.match(/^\s*\[(approved(?: \(modified\))?|rejected)\]/i);
    return match ? (match[1].toLowerCase() as ApprovalOutcome) : null;
}

export function actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase());
}

/** Builds a one-line sentence such as "Send r3 to charge" from an action and its subjects. */
export function actionSummary(action: string, robotId?: string | null, taskId?: string | null): string {
    switch (action) {
        case "operator_message":
            return "You sent an instruction";
        case "assign_task":
            return `Assign ${robotId ?? "a robot"} to task ${taskId ?? "?"}`;
        case "recall_to_charge":
            return `Send ${robotId ?? "a robot"} to charge`;
        case "reroute_robot":
            return `Reroute ${robotId ?? "a robot"}`;
        case "escalate_task":
            return `Flag task ${taskId ?? "?"} as failed for human follow-up`;
        default:
            return [actionLabel(action), robotId, taskId].filter(Boolean).join(" · ");
    }
}

/** Explains in plain language what approving an action will do, so supervisors know the real-world effect. */
export function approvalConsequence(action: string, robotId?: string | null, taskId?: string | null): string {
    switch (action) {
        case "escalate_task":
            return `Approve: task ${taskId ?? "?"} is marked failed and handed to a person to deal with (reschedule it or notify the customer). Reject: it stays in the queue.`;
        case "recall_to_charge":
            return `Approve: ${robotId ?? "the robot"} stops what it's doing and goes to charge; any job it was carrying returns to the queue. Reject: it keeps going.`;
        default:
            return "Approve to carry this out, or reject to leave things as they are.";
    }
}

export function cleanReasoning(reasoning: string): string {
    return reasoning.replace(REASONING_PREFIX, "").trim();
}

export function isPendingApproval(reasoning: string): boolean {
    return /\[pending approval\]/i.test(reasoning);
}

export function isLocalFallback(text: string): boolean {
    return /\[local fallback\]|local fallback/i.test(text);
}

/** Risks that repeat unchanged every cycle while the AI is down; shown once, not on every cycle. */
export function isRepeatingNotice(risk: string): boolean {
    return /^AI provider unavailable/i.test(risk);
}
