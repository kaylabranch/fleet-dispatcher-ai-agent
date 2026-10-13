/** Plain-language labels shared by the approval panel and the decision log. */

const ACTION_LABELS: Record<string, string> = {
    assign_task: "Assign task",
    reroute_robot: "Reroute robot",
    recall_to_charge: "Send to charge",
    escalate_task: "Escalate task",
    simulate_scenario: "Run what-if",
};

/** Prefixes the backend adds to reasoning text; they are shown as badges instead. */
const REASONING_PREFIX = /^\s*(\[pending approval\]|\[local fallback\])\s*/gi;

export function actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase());
}

/** Builds a one-line sentence such as "Send r3 to charge" from an action and its subjects. */
export function actionSummary(action: string, robotId?: string | null, taskId?: string | null): string {
    switch (action) {
        case "assign_task":
            return `Assign ${robotId ?? "a robot"} to task ${taskId ?? "?"}`;
        case "recall_to_charge":
            return `Send ${robotId ?? "a robot"} to charge`;
        case "reroute_robot":
            return `Reroute ${robotId ?? "a robot"}`;
        case "escalate_task":
            return `Escalate task ${taskId ?? "?"} to a human`;
        default:
            return [actionLabel(action), robotId, taskId].filter(Boolean).join(" · ");
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

/** Shortens noisy provider errors ("Gemini unavailable; local fallback dispatch used: ...") for display. */
export function cleanRisk(risk: string): string {
    if (/gemini unavailable/i.test(risk)) return "AI provider unavailable — using built-in fallback dispatch.";
    return risk;
}
