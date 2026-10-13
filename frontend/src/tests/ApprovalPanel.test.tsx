import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApprovalPanel } from "../ApprovalPanel";
import type { PendingApproval } from "../types";

const approval: PendingApproval = {
    id: "a1",
    action: "recall_to_charge",
    payload: { robot_id: "r3", reasoning: "battery low" },
    reasoning: "[pending approval] battery low",
    created_at: "2026-09-21T18:02:15Z",
    status: "pending",
};

describe("ApprovalPanel", () => {
    afterEach(() => vi.unstubAllGlobals());

    it("shows a friendly summary and removes the card after approving", async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
        vi.stubGlobal("fetch", fetchMock);
        render(<ApprovalPanel approvals={[approval]} />);

        expect(screen.getByText("Send r3 to charge")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Approve" }));

        await waitFor(() => expect(screen.queryByText("Send r3 to charge")).not.toBeInTheDocument());
        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:8000/approvals/a1",
            expect.objectContaining({ method: "POST" }),
        );
    });

    it("shows the server error and keeps the card when the request fails", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "Robot is broken" }) }));
        render(<ApprovalPanel approvals={[approval]} />);

        fireEvent.click(screen.getByRole("button", { name: "Reject" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Robot is broken");
        expect(screen.getByText("Send r3 to charge")).toBeInTheDocument();
    });
});
