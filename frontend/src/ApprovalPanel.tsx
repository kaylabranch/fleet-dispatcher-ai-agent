import { useState } from "react";
import type { PendingApproval } from "./types";

const API_URL = "http://localhost:8000";

interface ApprovalPanelProps {
    approvals: PendingApproval[];
}

/** Lists agent actions awaiting human approval and submits the review decision. */
export function ApprovalPanel({ approvals }: ApprovalPanelProps) {
    const [busyId, setBusyId] = useState<string | null>(null);

    async function resolve(approvalId: string, action: "approve" | "reject") {
        setBusyId(approvalId);
        try {
            const response = await fetch(`${API_URL}/approvals/${approvalId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action }),
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
                    </div>
                </div>
            ))}
        </div>
    );
}
