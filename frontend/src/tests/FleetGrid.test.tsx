import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FleetGrid } from "../FleetGrid";
import type { Robot, Task } from "../types";

const robot: Robot = {
    id: "r1",
    location: { x: 2, y: 5 },
    status: "idle",
    battery: 92,
    current_task_id: null,
    speed: 1,
    last_reported_at: null,
};

const task: Task = {
    id: "t1",
    pickup: { x: 1, y: 1 },
    dropoff: { x: 5, y: 5 },
    priority: "normal",
    deadline: null,
    status: "pending",
    assigned_robot_id: null,
};

describe("FleetGrid", () => {
    it("renders a marker for each robot and pending task", () => {
        const { container } = render(<FleetGrid robots={[robot]} tasks={[task]} />);
        expect(container.querySelector(`[title^="r1"]`)).toBeInTheDocument();
        expect(container.querySelector(`[title^="t1"]`)).toBeInTheDocument();
    });

    it("omits non-pending tasks from the grid", () => {
        const completedTask: Task = { ...task, status: "completed" };
        const { container } = render(<FleetGrid robots={[]} tasks={[completedTask]} />);
        expect(container.querySelector(`[title^="t1"]`)).not.toBeInTheDocument();
    });
});
