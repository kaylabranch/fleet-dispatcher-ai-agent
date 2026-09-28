import { useState } from "react";

const INTERVENE_URL = "http://localhost:8000/intervene";

/** Text input that POSTs a human intervention message for the agent's next cycle. */
export function ChatInput() {
    const [message, setMessage] = useState("");
    const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

    async function handleSubmit(event: React.FormEvent) {
        event.preventDefault();
        if (!message.trim()) return;

        setStatus("sending");
        try {
            const response = await fetch(INTERVENE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
            });
            if (!response.ok) throw new Error(`Request failed: ${response.status}`);
            setStatus("sent");
            setMessage("");
        } catch {
            setStatus("error");
        }
    }

    return (
        <form onSubmit={handleSubmit} className="flex w-full max-w-xl gap-2">
            <input
                type="text"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="e.g. recall r3 now"
                className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" disabled={status === "sending"}>
                Send
            </button>
            {status === "sent" && <span className="self-center text-xs text-green-600">Queued</span>}
            {status === "error" && <span className="self-center text-xs text-red-600">Failed</span>}
        </form>
    );
}
