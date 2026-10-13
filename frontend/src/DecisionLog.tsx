import type { DecisionLogEntry } from "./types";
import { actionSummary, approvalOutcome, cleanReasoning, cleanRisk, isLocalFallback, isPendingApproval } from "./actionLabels";

interface DecisionLogProps {
    entries: DecisionLogEntry[];
}

/** Streams the agent's decision history, most recent cycle first, skipping cycles with nothing to report. */
export function DecisionLog({ entries }: DecisionLogProps) {
    const visible = [...entries]
        .reverse()
        .filter((entry) => entry.decisions.length > 0 || entry.flagged_risks.length > 0);

    return (
        <div className="max-h-96 w-full max-w-xl overflow-y-auto rounded border border-gray-300">
            {visible.length === 0 && <p className="p-4 text-sm text-gray-500">No decisions logged yet.</p>}
            {visible.map((entry, entryIndex) => {
                const risks = [...new Set(entry.flagged_risks.map(cleanRisk))];
                return (
                    <div key={`${entry.cycle}-${entry.timestamp}-${entryIndex}`} className="border-b border-gray-200 p-3 last:border-b-0">
                        <div className="text-xs font-semibold text-gray-500">
                            Cycle {entry.cycle} — {new Date(entry.timestamp).toLocaleTimeString()}
                        </div>
                        <ul className="mt-1 space-y-2">
                            {entry.decisions.map((decision, index) => (
                                <li key={index} className="text-sm">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-medium">
                                            {actionSummary(decision.action, decision.robot_id, decision.task_id)}
                                        </span>
                                        {isPendingApproval(decision.reasoning) && (
                                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
                                                Needs your decision
                                            </span>
                                        )}
                                        {approvalOutcome(decision.reasoning) && (
                                            <span
                                                className={`rounded px-1.5 py-0.5 text-xs ${
                                                    approvalOutcome(decision.reasoning) === "rejected"
                                                        ? "bg-red-100 text-red-800"
                                                        : "bg-green-100 text-green-800"
                                                }`}
                                            >
                                                {approvalOutcome(decision.reasoning) === "rejected"
                                                    ? "Rejected"
                                                    : approvalOutcome(decision.reasoning) === "approved"
                                                      ? "Approved"
                                                      : "Approved (edited)"}
                                            </span>
                                        )}
                                        {isLocalFallback(decision.reasoning) && (
                                            <span
                                                title="The AI provider was unavailable, so a built-in rule made this suggestion."
                                                className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
                                            >
                                                Auto rule (no AI)
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-gray-600">{cleanReasoning(decision.reasoning)}</div>
                                </li>
                            ))}
                        </ul>
                        {risks.length > 0 && (
                            <ul className="mt-2 space-y-1">
                                {risks.map((risk, index) => (
                                    <li key={index} className="text-xs text-red-600">
                                        ⚠ {risk}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
