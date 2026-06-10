import os
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Ollama Chatbot")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = DEFAULT_MODEL


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML_PAGE)


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
        return {"status": "ok", "ollama": "connected", "models": models}
    except Exception as e:
        return {"status": "degraded", "ollama": "unreachable", "error": str(e)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Stream chat completions from Ollama."""

    async def stream_response():
        payload = {
            "model": req.model,
            "messages": [m.model_dump() for m in req.messages],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield f"data: {json.dumps({'token': token})}\n\n"
                            if data.get("done"):
                                yield "data: [DONE]\n\n"
                        except json.JSONDecodeError:
                            pass

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@app.get("/api/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
        return r.json()


# ── Inline HTML UI ────────────────────────────────────────────────────────────

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Ollama Chatbot</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }
  header { background: #1e293b; padding: 12px 20px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #334155; }
  header h1 { font-size: 1.1rem; font-weight: 600; }
  #model-select { background: #0f172a; color: #e2e8f0; border: 1px solid #475569; border-radius: 6px; padding: 4px 8px; font-size: 0.85rem; }
  #status-dot { width: 10px; height: 10px; border-radius: 50%; background: #64748b; margin-left: auto; }
  #status-dot.ok { background: #22c55e; }
  #status-dot.err { background: #ef4444; }
  #messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }
  .bubble { max-width: 75%; padding: 10px 14px; border-radius: 12px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
  .user { align-self: flex-end; background: #3b82f6; color: #fff; border-bottom-right-radius: 4px; }
  .assistant { align-self: flex-start; background: #1e293b; border-bottom-left-radius: 4px; }
  .thinking { opacity: 0.5; font-style: italic; }
  footer { padding: 14px 20px; background: #1e293b; border-top: 1px solid #334155; display: flex; gap: 10px; }
  #input { flex: 1; background: #0f172a; color: #e2e8f0; border: 1px solid #475569; border-radius: 8px; padding: 10px 14px; font-size: 0.95rem; resize: none; height: 44px; max-height: 140px; overflow-y: auto; }
  #input:focus { outline: none; border-color: #3b82f6; }
  #send-btn { background: #3b82f6; color: #fff; border: none; border-radius: 8px; padding: 0 18px; font-size: 0.95rem; cursor: pointer; }
  #send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  #send-btn:hover:not(:disabled) { background: #2563eb; }
  code { background: #0f172a; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 0.88em; }
</style>
</head>
<body>
<header>
  <h1>🦙 Ollama Chat</h1>
  <select id="model-select"><option value="">Loading models…</option></select>
  <div id="status-dot" title="Ollama status"></div>
</header>
<div id="messages"></div>
<footer>
  <textarea id="input" placeholder="Type a message… (Enter to send, Shift+Enter for newline)"></textarea>
  <button id="send-btn">Send</button>
</footer>

<script>
  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('send-btn');
  const modelSelect = document.getElementById('model-select');
  const statusDot = document.getElementById('status-dot');
  let history = [];

  // Load models and health
  async function init() {
    try {
      const r = await fetch('/health');
      const data = await r.json();
      statusDot.className = data.ollama === 'connected' ? 'ok' : 'err';
      const models = data.models || [];
      modelSelect.innerHTML = models.length
        ? models.map(m => `<option value="${m}">${m}</option>`).join('')
        : '<option value="">No models pulled yet</option>';
    } catch {
      statusDot.className = 'err';
    }
  }
  init();

  function addBubble(role, text, streaming = false) {
    const div = document.createElement('div');
    div.className = `bubble ${role}${streaming ? ' thinking' : ''}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text || sendBtn.disabled) return;
    inputEl.value = '';
    inputEl.style.height = '44px';

    history.push({ role: 'user', content: text });
    addBubble('user', text);

    sendBtn.disabled = true;
    const bubble = addBubble('assistant', '▌', true);
    let accumulated = '';

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, model: modelSelect.value }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6);
            if (payload === '[DONE]') break;
            try {
              const { token } = JSON.parse(payload);
              accumulated += token;
              bubble.textContent = accumulated;
              bubble.classList.remove('thinking');
              messagesEl.scrollTop = messagesEl.scrollHeight;
            } catch {}
          }
        }
      }
      history.push({ role: 'assistant', content: accumulated });
    } catch (e) {
      bubble.textContent = 'Error: ' + e.message;
      bubble.classList.remove('thinking');
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener('click', send);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    setTimeout(() => {
      inputEl.style.height = '44px';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
    }, 0);
  });
</script>
</body>
</html>"""
