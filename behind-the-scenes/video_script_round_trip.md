# Video script — AI Agent & MCP round trip (segment)

> Narration is in **English** — the submission video must be in English
> (`CONTEXT.md` §4). This covers only the "AI Agent & MCP Orchestration"
> segment: proving the chat message actually drives a real LLM → real MCP
> tool call → real World Bank API round trip, not a mock.

---

## Before you hit record

- Backend running: `cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000` (or your deployed URL).
- Frontend running: `cd frontend && npm run dev` (or your deployed URL), open in the browser.
- Terminal showing the backend logs, large enough font to read on screen —
  ideally side-by-side with the browser (split screen or picture-in-picture).
- Browser DevTools open on the **Network** tab, filtered to `chat`, ready to
  click into the request once it fires.
- Have your question typed but not sent yet, so you control the timing.

---

## Shot list (what to show, in order)

1. **Architecture diagram** (`docs/architecture.md`, section 2) on screen for
   2–3 seconds — orient the viewer before the demo: React → `/api/chat` →
   internal MCP client → `/mcp/` → World Bank API.
2. **Split screen**: browser (chat UI) on one side, backend terminal on the
   other.
3. **Type the question** in the chat box and hit send.
4. **While it's loading**, point at the terminal: the `POST /mcp/` calls and
   the outbound `GET https://api.worldbank.org/...` request appear live —
   this is the proof there's a real network call, not a canned answer.
5. **When the reply appears**, point at the small trace list under the
   assistant's bubble — it names the exact tool(s) called and their inputs.
6. **Click into the `/api/chat` request in DevTools → Response**, scroll to
   `history`: show the raw `tool_calls` and `role: "tool"` entries — the
   unedited machine record of the round trip, not something you typed up
   after the fact.
7. *(Optional, strong if time allows)* Open **MCP Inspector**
   (`npx @modelcontextprotocol/inspector`), connect it to `/mcp/` directly,
   list the 5 tools, run one manually — proves `/mcp/` is independently
   reachable by any MCP client, which is the literal "MCP endpoint URL"
   deliverable, not just an internal implementation detail of the chat.

---

## Text to read

> This part shows the actual round trip behind the chat: a user message,
> a real tool-calling LLM, and a real MCP server — no mocked data anywhere.
>
> Here's the architecture: the React frontend never talks to the LLM or to
> the MCP server directly. It calls `/api/chat`, which is the only place
> holding the model API key. That endpoint connects to `/mcp/` as an actual
> MCP client over Streamable HTTP — the same protocol any external MCP
> client, like MCP Inspector, could use — lists the five available tools,
> and hands them to the model.
>
> Watch what happens when I ask this question. On the right, you can see the
> backend logs: a request comes in on `/mcp/`, and right after it, a real
> outbound HTTP call to `api.worldbank.org`. That's the model deciding it
> needs data, calling the `search_indicators` and `get_latest_value` tools
> through the MCP session, and getting back real numbers — not something
> hardcoded in the backend.
>
> The reply appears with a small trace under it, listing exactly which tools
> were called and with what input — that's shown in the UI on purpose, as
> visible proof of execution, not just trust-me copy.
>
> And if I open the network response for this request, the full message
> history is right there in plain JSON — the tool call, its arguments, and
> the tool's result — exactly what was exchanged with the model, unedited.
>
> One engineering note worth mentioning here: I originally built this
> against Claude, then had to switch providers. Before locking in a model, I
> load-tested tool-calling reliability across a few Groq-hosted models on
> this exact tool set — `llama-3.3-70b-versatile` produced a malformed tool
> call roughly one time in three, which is not acceptable for a data
> product. `openai/gpt-oss-120b` ran five for five in the same test, so
> that's what's running here. That decision, and the cost/latency trade-offs
> behind it, are written up in the AI strategy document.

---

## After recording

`docs/ai_strategy.md` still documents the original Claude choice as the
retained model. Since the actual deployed model is now Groq
(`openai/gpt-oss-120b`), that document should be updated to match before
submission — the assessment explicitly penalizes claims that don't match
what's actually running (`CONTEXT.md` §6). Happy to draft that update when
you're ready.
