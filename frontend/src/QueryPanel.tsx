import { useState } from "react";

const API_URL = "http://localhost:8000";

/** Sends a read-only what-if request and displays the simulator summary. */
export function QueryPanel() {
    const [question, setQuestion] = useState("");
    const [result, setResult] = useState<string | null>(null);

    async function submit(event: React.FormEvent) {
        event.preventDefault();
        if (!question.trim()) return;
        const response = await fetch(`${API_URL}/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ hypothetical_change: question }),
        });
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        const payload = await response.json();
        setResult(payload.note ?? JSON.stringify(payload));
    }

    return (
        <div>
            <form onSubmit={(event) => void submit(event)} className="flex max-w-xl gap-2">
                <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="e.g. what if r1 went offline?"
                    className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
                />
                <button type="submit" className="rounded bg-purple-600 px-4 py-2 text-sm text-white">
                    Run simulation
                </button>
            </form>
            {result && <p className="mt-2 text-sm text-gray-600">{result}</p>}
        </div>
    );
}
