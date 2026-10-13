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
        expect(screen.getByText(/assign r1 to task t13/i)).toBeInTheDocument();
        expect(screen.getByText(/r1 is idle, closest to pickup/)).toBeInTheDocument();
        expect(screen.getByText(/deadline already passed on arrival/)).toBeInTheDocument();
    });

    it("hides internal prefixes and shows an approval badge", () => {
        const pending: DecisionLogEntry = {
            cycle: 7,
            timestamp: "2026-09-21T18:02:15Z",
            decisions: [{ action: "recall_to_charge", robot_id: "r3", task_id: null, reasoning: "[pending approval] battery low" }],
            flagged_risks: [],
        };
        render(<DecisionLog entries={[pending]} />);
        expect(screen.getByText("Send r3 to charge")).toBeInTheDocument();
        expect(screen.getByText("Needs your decision")).toBeInTheDocument();
        expect(screen.getByText("battery low")).toBeInTheDocument();
    });

    it("shows approval and rejection outcomes even when they share a cycle", () => {
        const make = (reasoning: string): DecisionLogEntry => ({
            cycle: 9,
            timestamp: "2026-09-21T18:02:15Z",
            decisions: [{ action: "recall_to_charge", robot_id: "r3", task_id: null, reasoning }],
            flagged_risks: [],
        });
        render(<DecisionLog entries={[make("[approved] battery low"), make("[rejected] battery low")]} />);
        expect(screen.getByText("Approved")).toBeInTheDocument();
        expect(screen.getByText("Rejected")).toBeInTheDocument();
        expect(screen.getAllByText("battery low")).toHaveLength(2);
    });

    it("shows operator instructions as a readable entry", () => {
        const message: DecisionLogEntry = {
            cycle: 5,
            timestamp: "2026-09-21T18:02:15Z",
            decisions: [{ action: "operator_message", robot_id: null, task_id: null, reasoning: "don't use r5 today" }],
            flagged_risks: [],
        };
        render(<DecisionLog entries={[message]} />);
        expect(screen.getByText("You sent an instruction")).toBeInTheDocument();
        expect(screen.getByText("don't use r5 today")).toBeInTheDocument();
    });

    it("skips cycles with no decisions or risks", () => {
        render(<DecisionLog entries={[{ cycle: 3, timestamp: "2026-09-21T18:02:15Z", decisions: [], flagged_risks: [] }]} />);
        expect(screen.getByText(/no decisions logged yet/i)).toBeInTheDocument();
    });
});


