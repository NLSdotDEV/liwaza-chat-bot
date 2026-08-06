import { useState } from "react";

const HINTS = [
  "Quel est le PIB de la Côte d'Ivoire ?",
  "Compare l'inflation avec le Ghana et le Sénégal",
  "Évolution de l'espérance de vie depuis 2000",
];

export default function App() {
  const [messages, setMessages] = useState([]);
  // Historique brut au format Anthropic, renvoyé au backend à chaque tour —
  // sans ça, chaque message serait traité comme une conversation neuve et le
  // LLM perdrait tout le contexte précédent dès le deuxième message.
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send(text) {
    const message = text.trim();
    if (!message || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessages((m) => [...m, { role: "assistant", content: data.detail || `Erreur (${res.status})`, trace: [] }]);
        return;
      }
      setHistory(data.history || []);
      setMessages((m) => [...m, { role: "assistant", content: data.reply, trace: data.trace }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Erreur réseau.", trace: [] }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Données publiques — Côte d'Ivoire</h1>
        <p>Posez une question en français ou en anglais.</p>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="hints">
            {HINTS.map((h) => (
              <button key={h} type="button" onClick={() => send(h)}>
                {h}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.trace?.length > 0 && (
              <ul className="trace">
                {m.trace.map((t, j) => (
                  <li key={j} className={t.is_error ? "err" : ""}>
                    {t.tool}({JSON.stringify(t.input)})
                  </li>
                ))}
              </ul>
            )}
            <div className="bubble">{m.content}</div>
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            <div className="bubble">…</div>
          </div>
        )}
      </main>

      <footer>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="Votre question…"
          disabled={loading}
        />
        <button type="button" onClick={() => send(input)} disabled={loading || !input.trim()}>
          Envoyer
        </button>
      </footer>
    </div>
  );
}
