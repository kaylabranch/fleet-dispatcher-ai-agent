import { useState } from "react";
import type { PendingApproval } from "./types";

const API_URL = "http://localhost:8000";

interface ApprovalPanelProps {
    approvals: PendingApproval[];
}

/** Lists agent actions awaiting human approval and submits the review decision. */
export function ApprovalPanel({ approvals }: ApprovalPanelProps) {
    const [busyId, setBusyId] = useState<string | null>(null);
    const [drafts, setDrafts] = useState<Record<string, string>>({});

    async function resolve(approvalId: string, action: "approve" | "reject" | "modify") {
        setBusyId(approvalId);
        try {
            const payload = action === "modify" ? JSON.parse(drafts[approvalId] ?? "{}") : undefined;
            const response = await fetch(`${API_URL}/approvals/${approvalId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action, payload }),
            });
            if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        } finally {
            setBusyId(null);
        }
    }

    return (
        <div className="rounded border border-gray-300">
            {approvals.length === 0 && (
                <div className="flex items-center justify-between p-4">
                    <p className="text-sm text-gray-500">No actions awaiting approval.</p>
                    <div className="flex gap-2">
                        <button type="button" disabled className="rounded bg-green-600 px-3 py-1 text-xs text-white disabled:opacity-50">
                            Approve
                        </button>
                        <button type="button" disabled className="rounded bg-gray-600 px-3 py-1 text-xs text-white disabled:opacity-50">
                            Reject
                        </button>
                    </div>
                </div>
            )}
            {approvals.map((approval) => (
                <div key={approval.id} className="border-b border-gray-200 p-3 last:border-b-0">
                    <div className="text-sm font-semibold">{approval.action}</div>
                    <div className="text-sm text-gray-600">{approval.reasoning}</div>
                    <textarea
                        aria-label={`Modify ${approval.action}`}
                        value={drafts[approval.id] ?? JSON.stringify(approval.payload, null, 2)}
                        onChange={(event) => setDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                        className="mt-2 h-24 w-full rounded border border-gray-300 p-2 font-mono text-xs"
                    />
                    <div className="mt-2 flex gap-2">
                        <button
                            type="button"
                            disabled={busyId === approval.id}
                            onClick={() => void resolve(approval.id, "approve")}
                            className="rounded bg-green-600 px-3 py-1 text-xs text-white disabled:opacity-50"
                        >
                            Approve
                        </button>
                        <button
                            type="button"
                            disabled={busyId === approval.id}
                            onClick={() => void resolve(approval.id, "reject")}
                            className="rounded bg-gray-600 px-3 py-1 text-xs text-white disabled:opacity-50"
                        >
                            Reject
                        </button>
                        <button
                            type="button"
                            disabled={busyId === approval.id}
                            onClick={() => void resolve(approval.id, "modify")}
                            className="rounded bg-blue-600 px-3 py-1 text-xs text-white disabled:opacity-50"
                        >
                            Modify & apply
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}
