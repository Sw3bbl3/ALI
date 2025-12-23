"""Web UI interface for ALI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict

from ali.core.event_bus import Event, EventBus

HTML_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>ALI Live Console</title>
    <style>
      body {
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
        background: #0b1020;
        color: #e6e6f0;
      }
      header {
        padding: 16px 24px;
        background: #11172b;
        border-bottom: 1px solid #1e2945;
      }
      main {
        display: grid;
        grid-template-columns: 1.1fr 1fr;
        gap: 16px;
        padding: 16px 24px;
      }
      section {
        background: #121a33;
        border: 1px solid #1f2b4f;
        border-radius: 12px;
        padding: 16px;
        min-height: 420px;
      }
      h2 {
        margin: 0 0 12px 0;
        font-size: 16px;
        color: #c5d0f0;
      }
      .payload {
        white-space: pre-wrap;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        color: #d7def7;
        margin-top: 6px;
      }
      .event-meta {
        color: #94a1c3;
        font-size: 12px;
      }
      .input-row {
        display: flex;
        gap: 8px;
      }
      input[type="text"] {
        flex: 1;
        padding: 10px 12px;
        border-radius: 8px;
        border: 1px solid #2b3a66;
        background: #0b1226;
        color: #e6e6f0;
      }
      button {
        padding: 10px 16px;
        border-radius: 8px;
        border: none;
        background: #4f7cff;
        color: #fff;
        cursor: pointer;
        font-weight: 600;
      }
      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .panel-card {
        border: 1px solid #2b3a66;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        background: #0f1730;
      }
      .panel-card h3 {
        margin: 0 0 8px 0;
        font-size: 14px;
        color: #9ad5ff;
      }
      .tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        background: #1e2b52;
        color: #9ad5ff;
        font-size: 11px;
        margin-right: 6px;
      }
      .intent-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }
      .intent-grid div {
        font-size: 12px;
        color: #cbd5f5;
      }
      .intent-grid strong {
        color: #f7c948;
        font-weight: 600;
      }
      .response-card h3 {
        color: #7ae7c7;
      }
    </style>
  </head>
  <body>
    <header>
      <h1>ALI Live Console</h1>
      <p>Send messages while tracking real-time intent and responses.</p>
    </header>
    <main>
      <section>
        <h2>Send message</h2>
        <div class="input-row">
          <input id="messageInput" type="text" placeholder="Type a message to ALI..." />
          <button id="sendButton">Send</button>
        </div>
        <p id="statusLine"></p>
        <h2>Live intent</h2>
        <div class="panel-card" id="intentCard">
          <h3 id="intentTitle">Waiting for intent...</h3>
          <div class="intent-grid">
            <div>Intent: <strong id="intentValue">idle</strong></div>
            <div>Confidence: <strong id="intentConfidence">0.00</strong></div>
            <div>Emotion: <strong id="intentEmotion">neutral</strong></div>
            <div>Updated: <strong id="intentUpdated">--</strong></div>
          </div>
          <div class="payload" id="intentDetails"></div>
        </div>
      </section>
      <section>
        <h2>ALI responses</h2>
        <div id="responseStream"></div>
      </section>
    </main>
    <script>
      const statusLine = document.getElementById("statusLine");
      const responseStream = document.getElementById("responseStream");
      const messageInput = document.getElementById("messageInput");
      const sendButton = document.getElementById("sendButton");
      const intentTitle = document.getElementById("intentTitle");
      const intentValue = document.getElementById("intentValue");
      const intentConfidence = document.getElementById("intentConfidence");
      const intentEmotion = document.getElementById("intentEmotion");
      const intentUpdated = document.getElementById("intentUpdated");
      const intentDetails = document.getElementById("intentDetails");

      function prettyJson(obj) {
        return JSON.stringify(obj, null, 2);
      }

      function updateIntent(event) {
        intentTitle.textContent = event.payload.transcript
          ? `Heard: "${event.payload.transcript}"`
          : "Live intent update";
        intentValue.textContent = event.payload.intent || "idle";
        intentConfidence.textContent = Number(event.payload.confidence || 0).toFixed(2);
        intentEmotion.textContent = event.payload.emotion || "neutral";
        intentUpdated.textContent = event.created_at || "--";
        intentDetails.textContent = prettyJson({
          context_tags: event.payload.context_tags || [],
          source_event: event.payload.source_event,
        });
      }

      function addResponse(event) {
        const item = document.createElement("div");
        item.className = "panel-card response-card";
        const title = event.payload.title ? ` - ${event.payload.title}` : "";
        item.innerHTML = `
          <h3>${event.payload.response_type || "response"}${title}</h3>
          <div class="event-meta">source: ${event.source} • ${event.created_at}</div>
          <div class="payload">${event.payload.message || event.payload.text || ""}</div>
        `;
        responseStream.prepend(item);
        if (responseStream.children.length > 20) {
          responseStream.removeChild(responseStream.lastChild);
        }
      }

      const source = new EventSource("/api/events");
      source.onmessage = (message) => {
        const event = JSON.parse(message.data);
        if (event.event_type === "intent.updated") {
          updateIntent(event);
        }
        if (event.event_type === "ali.response") {
          addResponse(event);
        }
      };
      source.onerror = () => {
        statusLine.textContent = "Connection lost. Retrying...";
      };

      async function sendMessage() {
        const text = messageInput.value.trim();
        if (!text) return;
        sendButton.disabled = true;
        statusLine.textContent = "Sending...";
        try {
          const response = await fetch("/api/message", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: text})
          });
          if (!response.ok) {
            throw new Error("Request failed");
          }
          messageInput.value = "";
          statusLine.textContent = "Sent.";
        } catch (err) {
          statusLine.textContent = "Failed to send.";
        } finally {
          sendButton.disabled = false;
        }
      }

      sendButton.addEventListener("click", sendMessage);
      messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          sendMessage();
        }
      });
    </script>
  </body>
</html>
"""


class WebUiServer:
    """Lightweight HTTP server that streams events and accepts messages."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._logger = logging.getLogger("ali.interface.web")
        self._host = os.getenv("ALI_WEB_UI_HOST", "127.0.0.1")
        port_setting = os.getenv("ALI_WEB_UI_PORT")
        self._port_is_fixed = False
        if port_setting is None:
            self._port = 8080
        elif port_setting.lower() in {"auto", "0"}:
            self._port = 0
        else:
            self._port = int(port_setting)
            self._port_is_fixed = True
        self._server: asyncio.AbstractServer | None = None
        self._subscribers: set[asyncio.Queue[Dict[str, Any]]] = set()
        self._ui_event_types = {"intent.updated", "ali.response"}

    async def run(self) -> None:
        """Start the web UI server and keep it running."""
        await self._event_bus.subscribe("*", self._handle_event)
        await self._start_server()
        sockets = ", ".join(str(sock.getsockname()) for sock in self._server.sockets or [])
        url_host = "127.0.0.1" if self._host == "0.0.0.0" else self._host
        self._logger.info("Web UI listening on %s", sockets)
        self._logger.info("Open http://%s:%s in your browser", url_host, self._port)
        async with self._server:
            await self._server.serve_forever()

    async def _start_server(self) -> None:
        if self._port == 0:
            self._server = await asyncio.start_server(self._handle_connection, self._host, 0)
            self._port = (self._server.sockets or [])[0].getsockname()[1]
            return
        ports = [self._port]
        if not self._port_is_fixed:
            ports.extend(range(self._port + 1, self._port + 11))
        last_error: Exception | None = None
        for port in ports:
            try:
                self._server = await asyncio.start_server(self._handle_connection, self._host, port)
                self._port = port
                return
            except OSError as exc:
                last_error = exc
        if last_error:
            raise last_error

    async def _handle_event(self, event: Event) -> None:
        if event.event_type not in self._ui_event_types:
            return
        payload = {
            "event_type": event.event_type,
            "source": event.source,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return
            method, path, _ = request_line.decode().strip().split(" ", maxsplit=2)
            headers = await self._read_headers(reader)
            if method == "GET" and path == "/":
                await self._send_response(writer, 200, "text/html", HTML_PAGE.encode())
            elif method == "GET" and path == "/api/events":
                await self._stream_events(writer)
            elif method == "POST" and path == "/api/message":
                await self._handle_message(reader, writer, headers)
            else:
                await self._send_response(writer, 404, "text/plain", b"Not found")
        except Exception as exc:  # pragma: no cover - defensive server loop
            self._logger.error("Web UI connection error: %s", exc)
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def _read_headers(self, reader: asyncio.StreamReader) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            key, value = line.decode().split(":", maxsplit=1)
            headers[key.strip().lower()] = value.strip()
        return headers

    async def _handle_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, headers: Dict[str, str]
    ) -> None:
        length = int(headers.get("content-length", "0"))
        body = await reader.readexactly(length) if length else b"{}"
        try:
            payload = json.loads(body.decode())
            message = payload.get("message", "")
            await self._event_bus.publish(
                Event(
                    event_type="speech.transcript",
                    payload={
                        "transcript": message,
                        "confidence": 0.9,
                        "intent_hints": [],
                        "source_event": "web_ui.input",
                    },
                    source="web_ui.input",
                )
            )
            await self._send_response(writer, 200, "application/json", b"{\"ok\": true}")
        except json.JSONDecodeError:
            await self._send_response(writer, 400, "application/json", b"{\"ok\": false}")

    async def _stream_events(self, writer: asyncio.StreamWriter) -> None:
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n\r\n"
        )
        writer.write(headers.encode())
        await writer.drain()
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=20)
        self._subscribers.add(queue)
        try:
            while True:
                payload = await queue.get()
                data = json.dumps(payload, default=str)
                writer.write(f"data: {data}\n\n".encode())
                await writer.drain()
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self._subscribers.discard(queue)

    async def _send_response(self, writer: asyncio.StreamWriter, status: int, mime: str, body: bytes) -> None:
        reason = "OK" if status == 200 else "Not Found"
        if status == 400:
            reason = "Bad Request"
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {mime}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(header.encode() + body)
        await writer.drain()
