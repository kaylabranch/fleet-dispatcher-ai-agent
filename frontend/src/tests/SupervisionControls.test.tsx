import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useFleetSocket", () => ({
    useFleetSocket: () => ({
        fleet: { cycle: 0, robots: [], tasks: [], recent_events: [] },
        decisions: [],
        connected: true,
    }),
}));

import { Dashboard } from "../Dashboard";

describe("Dashboard human supervision", () => {
    it("lets a supervisor review and resolve pending approvals", () => {
        render(<Dashboard />);

        expect(screen.getByRole("heading", { name: /pending approvals/i })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    });

    it("provides a read-only what-if query control", () => {
        render(<Dashboard />);

        expect(screen.getByRole("heading", { name: /what-if query/i })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /run simulation/i })).toBeInTheDocument();
    });
});
