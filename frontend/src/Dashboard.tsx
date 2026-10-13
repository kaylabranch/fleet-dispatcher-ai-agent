import { DecisionLog } from "./DecisionLog";
import { FleetGrid } from "./FleetGrid";
import { ChatInput } from "./ChatInput";
import { ApprovalPanel } from "./ApprovalPanel";
import { QueryPanel } from "./QueryPanel";
import { useFleetSocket } from "./hooks/useFleetSocket";

/** Top-level dashboard: fleet grid, live decision log, and the intervention chat input. */
export function Dashboard() {
    const { fleet, decisions, approvals = [], connected } = useFleetSocket();

    return (
        <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
            <header className="flex items-center justify-between">
                <h1 className="text-xl font-bold">Fleet Dispatch Agent</h1>
                <span className={`text-sm ${connected ? "text-green-600" : "text-gray-400"}`}>
                    {connected ? "● connected" : "○ disconnected"}
                </span>
            </header>

            <div className="grid gap-6 md:grid-cols-2">
                <section>
                    <h2 className="mb-2 text-sm font-semibold text-gray-700">Fleet Grid</h2>
                    <FleetGrid robots={fleet?.robots ?? []} tasks={fleet?.tasks ?? []} />
                </section>

                <section>
                    <h2 className="mb-2 text-sm font-semibold text-gray-700">Decision Log</h2>
                    <DecisionLog entries={decisions} />
                </section>
            </div>

            <section>
                <h2 className="mb-2 text-sm font-semibold text-gray-700">Intervene</h2>
                <ChatInput />
            </section>

            <section>
                <h2 className="mb-2 text-sm font-semibold text-gray-700">Pending approvals</h2>
                <ApprovalPanel approvals={approvals} />
            </section>

            <section>
                <h2 className="mb-2 text-sm font-semibold text-gray-700">What-if query</h2>
                <QueryPanel />
            </section>
        </div>
    );
}
