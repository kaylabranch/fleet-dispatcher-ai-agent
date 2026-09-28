import type { DecisionLogEntry } from "./types";

interface DecisionLogProps {
    entries: DecisionLogEntry[];
}

/** Streams the agent's decision history, most recent cycle first, with reasoning visible. */
export function DecisionLog({ entries }: DecisionLogProps) {
    const reversed = [...entries].reverse();

    return (
        <div className="max-h-96 w-full max-w-xl overflow-y-auto rounded border border-gray-300">
            {reversed.length === 0 && <p className="p-4 text-sm text-gray-500">No decisions logged yet.</p>}
            {reversed.map((entry) => (
                <div key={entry.cycle} className="border-b border-gray-200 p-3 last:border-b-0">
                    <div className="text-xs font-semibold text-gray-500">
                        Cycle {entry.cycle} — {new Date(entry.timestamp).toLocaleTimeString()}
                    </div>
                    <ul className="mt-1 space-y-1">
                        {entry.decisions.map((decision, index) => (
                            <li key={index} className="text-sm">
                                <span className="font-medium">{decision.action}</span>
                                {decision.robot_id && ` · ${decision.robot_id}`}
                                {decision.task_id && ` · ${decision.task_id}`}
                                <div className="text-gray-600">{decision.reasoning}</div>
                            </li>
                        ))}
                    </ul>
                    {entry.flagged_risks.length > 0 && (
                        <ul className="mt-1 space-y-1">
                            {entry.flagged_risks.map((risk, index) => (
                                <li key={index} className="text-sm text-red-600">
                                    ⚠ {risk}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            ))}
        </div>
    );
}
