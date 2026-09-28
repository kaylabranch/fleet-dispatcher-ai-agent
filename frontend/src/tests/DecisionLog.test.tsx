import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionLog } from "../DecisionLog";
import type { DecisionLogEntry } from "../types";

const entry: DecisionLogEntry = {
    cycle: 42,
    timestamp: "2026-09-21T18:02:15Z",
    decisions: [
        {
            action: "assign_task",
            robot_id: "r1",
            task_id: "t13",
            reasoning: "r1 is idle, closest to pickup",
        },
    ],
    flagged_risks: ["t14 deadline already passed on arrival"],
};

describe("DecisionLog", () => {
    it("shows a placeholder when there are no entries", () => {
        render(<DecisionLog entries={[]} />);
        expect(screen.getByText(/no decisions logged yet/i)).toBeInTheDocument();
    });

    it("renders decisions and flagged risks for each cycle", () => {
        render(<DecisionLog entries={[entry]} />);
        expect(screen.getByText(/cycle 42/i)).toBeInTheDocument();
        expect(screen.getByText(/assign_task/)).toBeInTheDocument();
        expect(screen.getByText(/r1 is idle, closest to pickup/)).toBeInTheDocument();
        expect(screen.getByText(/deadline already passed on arrival/)).toBeInTheDocument();
    });
});
