import type { Robot, Task } from "./types";

interface FleetGridProps {
    robots: Robot[];
    tasks: Task[];
}

const GRID_SIZE = 10;

const STATUS_COLORS: Record<Robot["status"], string> = {
    idle: "bg-green-500",
    en_route: "bg-blue-500",
    charging: "bg-yellow-500",
    broken: "bg-red-500",
};

/** Renders robots and pending task pickups on a simple abstract grid. */
export function FleetGrid({ robots, tasks }: FleetGridProps) {
    const pendingTasks = tasks.filter((task) => task.status === "pending");

    return (
        <div className="relative aspect-square w-full max-w-xl border border-gray-300 bg-gray-50">
            {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => (
                <div
                    key={`line-${i}`}
                    className="absolute border-gray-200"
                    style={{
                        left: `${(i / GRID_SIZE) * 100}%`,
                        top: 0,
                        bottom: 0,
                        borderLeftWidth: 1,
                    }}
                />
            ))}

            {pendingTasks.map((task) => (
                <div
                    key={task.id}
                    title={`${task.id} (${task.priority})`}
                    className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 bg-purple-400"
                    style={{
                        left: `${(task.pickup.x / GRID_SIZE) * 100}%`,
                        top: `${(task.pickup.y / GRID_SIZE) * 100}%`,
                    }}
                />
            ))}

            {robots.map((robot) => (
                <div
                    key={robot.id}
                    title={`${robot.id} — ${robot.status}, ${robot.battery}% battery`}
                    className={`absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${STATUS_COLORS[robot.status]}`}
                    style={{
                        left: `${(robot.location.x / GRID_SIZE) * 100}%`,
                        top: `${(robot.location.y / GRID_SIZE) * 100}%`,
                    }}
                />
            ))}
        </div>
    );
}
