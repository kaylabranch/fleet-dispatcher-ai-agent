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

const STATUS_LABELS: Record<Robot["status"], string> = {
    idle: "Idle",
    en_route: "En route",
    charging: "Charging",
    broken: "Broken",
};

function position(value: number): string {
    return `${(value / GRID_SIZE) * 100}%`;
}

/** Renders a labeled fleet map with robot paths, task locations, coordinates, and a legend. */
export function FleetGrid({ robots, tasks }: FleetGridProps) {
    const pendingTasks = tasks.filter((task) => task.status === "pending");
    const taskById = new Map(tasks.map((task) => [task.id, task]));

    return (
        <div>
            <div className="mb-1 ml-8 flex justify-between text-[10px] text-gray-500">
                {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => <span key={`x-${i}`}>{i}</span>)}
            </div>
            <div className="flex">
                <div className="flex w-7 flex-col justify-between py-1 text-right text-[10px] text-gray-500">
                    {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => <span key={`y-${i}`}>{i}</span>)}
                </div>
                <div className="relative aspect-square min-w-0 flex-1 border border-gray-300 bg-gray-50">
            {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => (
                <div
                    key={`line-${i}`}
                    className="absolute border-gray-200"
                    style={{
                        left: position(i),
                        top: 0,
                        bottom: 0,
                        borderLeftWidth: 1,
                    }}
                />
            ))}
            {Array.from({ length: GRID_SIZE + 1 }).map((_, i) => (
                <div
                    key={`row-${i}`}
                    className="absolute border-gray-200"
                    style={{ top: position(i), left: 0, right: 0, borderTopWidth: 1 }}
                />
            ))}

            {pendingTasks.map((task) => (
                <div key={task.id}>
                    <div
                        title={`${task.id} (${task.priority}) pickup`}
                        className="absolute z-10 flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 items-center justify-center bg-purple-500"
                        style={{ left: position(task.pickup.x), top: position(task.pickup.y) }}
                    >
                        <span className="-rotate-45 text-[8px] font-bold text-white">P</span>
                    </div>
                    <div
                        title={`${task.id} dropoff`}
                        className="absolute z-10 flex h-4 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-purple-700 bg-white text-[8px] font-bold text-purple-700"
                        style={{ left: position(task.dropoff.x), top: position(task.dropoff.y) }}
                    >
                        D
                    </div>
                    <span
                        className="absolute z-20 whitespace-nowrap rounded bg-white/80 px-1 text-[10px] font-semibold text-purple-800"
                        style={{ left: `calc(${position(task.pickup.x)} + 8px)`, top: `calc(${position(task.pickup.y)} - 18px)` }}
                    >
                        {task.id}
                    </span>
                </div>
            ))}

            <svg className="pointer-events-none absolute inset-0 z-0 h-full w-full" viewBox="0 0 100 100" aria-label="Robot routes">
                {robots.filter((robot) => robot.status === "en_route").map((robot) => {
                    const task = robot.current_task_id ? taskById.get(robot.current_task_id) : undefined;
                    const destination = task?.status === "in_progress" ? task.dropoff : task?.pickup;
                    const points = [robot.location, ...robot.route, ...(destination ? [destination] : [])];
                    return points.length > 1 ? (
                        <polyline
                            key={`route-${robot.id}`}
                            points={points.map((point) => `${(point.x / GRID_SIZE) * 100},${(point.y / GRID_SIZE) * 100}`).join(" ")}
                            fill="none"
                            stroke="#2563eb"
                            strokeDasharray="3 2"
                            strokeWidth="0.6"
                            vectorEffect="non-scaling-stroke"
                        />
                    ) : null;
                })}
            </svg>

            {robots.map((robot) => (
                <div key={robot.id}>
                    <div
                        title={`${robot.id} — ${STATUS_LABELS[robot.status]}, ${robot.battery}% battery`}
                        className={`absolute z-30 flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white text-[8px] font-bold text-white shadow ${STATUS_COLORS[robot.status]}`}
                        style={{ left: position(robot.location.x), top: position(robot.location.y) }}
                    >
                        {robot.id}
                    </div>
                    <span
                        className="absolute z-20 whitespace-nowrap rounded bg-white/80 px-1 text-[10px] font-semibold text-gray-700"
                        style={{ left: `calc(${position(robot.location.x)} + 8px)`, top: `calc(${position(robot.location.y)} + 6px)` }}
                    >
                        {robot.status} · {robot.battery.toFixed(0)}%
                    </span>
                </div>
            ))}
                </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-600" aria-label="Map legend">
                {(Object.keys(STATUS_COLORS) as Robot["status"][]).map((status) => (
                    <span key={status} className="flex items-center gap-1">
                        <span className={`h-3 w-3 rounded-full ${STATUS_COLORS[status]}`} />
                        {STATUS_LABELS[status]}
                    </span>
                ))}
                <span className="flex items-center gap-1"><span className="h-3 w-3 rotate-45 bg-purple-500" /> Pickup</span>
                <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-full border-2 border-purple-700" /> Drop-off</span>
                <span className="text-gray-500">Dashed line = planned route · coordinates are grid x/y</span>
            </div>
            <p className="mt-2 text-xs text-gray-500">Robot markers move after each running simulation cycle. Select a robot marker for its status, battery, and current task.</p>
        </div>
    );
}
