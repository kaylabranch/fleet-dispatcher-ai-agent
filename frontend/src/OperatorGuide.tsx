import type { SimulationStatus } from "./types";

interface OperatorGuideProps {
    status: SimulationStatus;
}

/** Explains the next operator action directly inside the dashboard. */
export function OperatorGuide({ status }: OperatorGuideProps) {
    const steps = status === "running"
        ? [
            "Watch the fleet grid: robot markers move after each cycle.",
            "Read the decision log to understand Gemini's reasoning.",
            "Use Intervene for human instructions or review Pending approvals.",
        ]
        : [
            "Choose a scenario above.",
            "Click Start to run the first cycle immediately.",
            "Then watch robot movement, decisions, events, and approvals.",
        ];

    return (
        <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800">What to do</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-gray-600">
                {steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
            {status === "running" && (
                <p className="mt-3 text-xs text-blue-700">
                    The simulation is running autonomously. You only need to act when an approval
                    appears or you want to send an intervention.
                </p>
            )}
        </section>
    );
}
