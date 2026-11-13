"""Servidor Web para a EVA OS."""

import asyncio
import json
from typing import Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from src.kernel.events import Event, EventBus
from src.core.event_types import EventType

import hmac
import ipaddress
import os
import re
import threading
from collections import deque, OrderedDict
from copy import deepcopy


class MessageRequest(BaseModel):
    text: str
    user: str = "Alberto"
    mode: str = "normal"
    session_id: str | None = None


class WebServer:
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self.app = FastAPI(title="EVA OS Web Interface", version="2.0.0")
        self._active_websockets: Set[WebSocket] = set()
        self._running = False
        self._initialized = False
        self._shutdown_in_progress = False
        self._lifecycle_lock = asyncio.Lock()
        self._server = None
        self._server_task = None
        self._server_port = None
        self._web_events_subscribed = False
        self._web_listener_bindings = (
            (EventType.ASSISTANT_RESPONSE, self._on_response),
            (EventType.PROCESSING_START, self._on_processing_start),
            (EventType.PROCESSING_END, self._on_processing_end),
            (EventType.COGNITIVE_ERROR, self._on_error),
            ("reminder.notification", self._on_reminder),
            ("pipeline.status", self._on_pipeline_status),
        )
        self._setup_routes()
        self._setup_websocket()
        self._setup_static()
        self._setup_network_alerts()
        self._subscribe_web_events()
        self.logger.info("WebServer: construido; HTTP ainda nao iniciado")

    def _setup_network_alerts(self):
        self._network_alerts_lock = threading.Lock()
        self._network_alerts_events = deque(maxlen=100)
        self._network_alerts_seen = OrderedDict()
        self._network_alerts_cursor = 0
        self._network_alerts_active = False
        self._subscribe_network_alerts()
        self.app.add_api_route(
            "/security/network-alerts", self._get_network_alerts,
            methods=["GET"], response_class=JSONResponse,
        )

    def _subscribe_network_alerts(self):
        with self._network_alerts_lock:
            if self._network_alerts_active:
                return
            self._network_alerts_active = True
        self.event_bus.subscribe("security.network.alert", self._on_network_alert)
        self.event_bus.subscribe("security.network.recovered", self._on_network_alert)

    def _stop_network_alerts(self):
        with self._network_alerts_lock:
            if not self._network_alerts_active:
                return
            self._network_alerts_active = False
            self._network_alerts_events.clear()
            self._network_alerts_seen.clear()
        try:
            self.event_bus.unsubscribe("security.network.alert", self._on_network_alert)
            self.event_bus.unsubscribe("security.network.recovered", self._on_network_alert)
        except AttributeError:
            self.logger.warning("EventBus sem método unsubscribe — ignorando")

    @staticmethod
    def _network_alert_key():
        key = os.environ.get("EVA_NETWORK_ALERTS_KEY", "")
        if re.fullmatch(r"[A-Za-z0-9_-]{43,128}", key):
            return key
        return None

    async def _on_network_alert(self, event):
        kind = getattr(event, "type", None)
        expected_state = {
            "security.network.alert": "unavailable",
            "security.network.recovered": "available",
        }.get(kind)
        payload = getattr(event, "data", None)
        if (not expected_state or getattr(event, "source", None) != "security"
                or not isinstance(payload, dict)
                or payload.get("scope") != "connectivity_only"):
            return
        target = payload.get("target")
        identifier = payload.get("notification_id")
        if (not isinstance(target, dict)
                or not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier)
                or not isinstance(target.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", target["id"])
                or target.get("state") != expected_state):
            return
        checked_at = target.get("checked_at")
        if not isinstance(checked_at, str) or not 1 <= len(checked_at) <= 64:
            return
        message = (
            "Conectividade nao confirmada apos falhas consecutivas."
            if expected_state == "unavailable"
            else "Conectividade confirmada apos sucessos consecutivos."
        )
        with self._network_alerts_lock:
            if not self._network_alerts_active or identifier in self._network_alerts_seen:
                return
            self._network_alerts_seen[identifier] = None
            while len(self._network_alerts_seen) > 512:
                self._network_alerts_seen.popitem(last=False)
            self._network_alerts_cursor += 1
            self._network_alerts_events.append({
                "sequence": self._network_alerts_cursor,
                "type": kind,
                "notification_id": identifier,
                "scope": "connectivity_only",
                "target": {"id": target["id"], "state": expected_state},
                "checked_at": checked_at,
                "message": message,
            })

    async def _get_network_alerts(self, request: Request):
        headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}

        def response(body, status=200):
            return JSONResponse(body, status_code=status, headers=headers)

        with self._network_alerts_lock:
            active = self._network_alerts_active
            expected_key = self._network_alert_key()
            if not active or expected_key is None:
                return response({"error": "alert_channel_unavailable"}, 503)

            try:
                scheme = request.url.scheme
                hostname = request.url.hostname
                if scheme == "http":
                    client_local = (
                        request.client is not None
                        and ipaddress.ip_address(request.client.host).is_loopback
                    )
                    try:
                        host_local = ipaddress.ip_address(hostname).is_loopback
                    except ValueError:
                        host_local = hostname == "localhost"
                    if not client_local or not host_local:
                        return response({"error": "secure_transport_required"}, 403)
                elif scheme != "https":
                    return response({"error": "secure_transport_required"}, 403)
                origin = request.headers.get("origin")
                if origin is not None and origin != scheme + "://" + request.url.netloc:
                    return response({"error": "origin_denied"}, 403)
            except (ValueError, TypeError):
                return response({"error": "connection_denied"}, 403)

            if request.headers.get("sec-fetch-site") == "cross-site":
                return response({"error": "origin_denied"}, 403)

            authorization = request.headers.get("authorization", "")
            token = authorization[7:] if authorization.startswith("Bearer ") else ""
            if (not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token)
                    or not hmac.compare_digest(token, expected_key)):
                return response({"error": "access_denied"}, 401)

            if any(key != "after" for key in request.query_params):
                return response({"error": "invalid_query"}, 400)
            values = request.query_params.getlist("after")
            raw = values[0] if values else "0"
            if len(values) > 1 or not re.fullmatch(r"[0-9]{1,16}", raw):
                return response({"error": "invalid_cursor"}, 400)
            after = int(raw)

            with self._network_alerts_lock:
                if not self._network_alerts_active:
                    return response({"error": "alert_channel_unavailable"}, 503)
                cursor = self._network_alerts_cursor
                oldest = (
                    self._network_alerts_events[0]["sequence"]
                    if self._network_alerts_events else cursor + 1
                )
                reset = after > cursor
                gap = reset or after < oldest - 1
                events = [
                    deepcopy(item) for item in self._network_alerts_events
                    if reset or item["sequence"] > after
                ]
                return response({
                    "scope": "connectivity_only",
                    "cursor": cursor,
                    "gap": gap,
                    "events": events,
                })

    def _subscribe_web_events(self):
        if self._web_events_subscribed:
            return
        for name, callback in self._web_listener_bindings:
            self.event_bus.subscribe(name, callback)
        self._web_events_subscribed = True

    def _unsubscribe_web_events(self):
        if not self._web_events_subscribed:
            return
        for name, callback in self._web_listener_bindings:
            try:
                self.event_bus.unsubscribe(name, callback)
            except AttributeError:
                self.logger.warning(f"EventBus sem unsubscribe: {name} mantido")
        self._web_events_subscribed = False

    async def _stop_http(self):
        server = self._server
        task = self._server_task
        try:
            if server is not None:
                server.should_exit = True
            if task is not None:
                completion = asyncio.gather(task, return_exceptions=True)
                try:
                    await asyncio.wait_for(asyncio.shield(completion), timeout=5)
                except asyncio.TimeoutError:
                    if server is not None:
                        server.force_exit = True
                        for connection in list(server.server_state.connections):
                            transport = getattr(connection, "transport", None)
                            if transport is not None:
                                transport.abort()
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                listeners = list(getattr(server, "servers", [])) if server is not None else []
                for listener in listeners:
                    listener.close()
                if listeners:
                    await asyncio.wait_for(asyncio.gather(
                        *(listener.wait_closed() for listener in listeners)
                    ), timeout=2)
        finally:
            self._running = False
            self._server = None
            self._server_task = None
            self._server_port = None

    def _setup_static(self) -> None:
        web_path = Path(__file__).parent.parent.parent.parent / "web"
        if web_path.exists():
            self.app.mount("/static", StaticFiles(directory=str(web_path)), name="static")
 
    def _setup_routes(self) -> None:
        @self.app.get("/")
        async def index():
            web_path = Path(__file__).parent.parent.parent.parent / "web" / "index.html"
            if web_path.exists():
                return FileResponse(str(web_path))
            return JSONResponse({"error": "Interface não encontrada"}, status_code=404)
        
        @self.app.get("/status")
        async def status():
            return {
                "status": "running" if self._running else "stopped",
                "websockets": len(self._active_websockets),
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/api/system/info")
        async def api_system_info():
            return {"status": "operational", "version": "1.0.0"}

        @self.app.get("/api/agents/status")
        async def api_agents_status():
            return {"agents": ["general", "memory", "planner"], "timestamp": datetime.now().isoformat()}
        
        @self.app.post("/message")
        async def message(request: MessageRequest):
            await self.event_bus.publish_async(
                EventType.USER_MESSAGE,
                {
                    "text": request.text,
                    "user": request.user,
                    "mode": request.mode,
                    "session_id": request.session_id,
                    "source": "web",
                    "timestamp": datetime.now().isoformat()
                },
                source="web_server"
            )
            return {"status": "received", "timestamp": datetime.now().isoformat()}
 
    def _setup_websocket(self) -> None:
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._active_websockets.add(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                if websocket in self._active_websockets:
                    self._active_websockets.remove(websocket)
            except Exception as e:
                self.logger.error(f"❌ Erro no WebSocket: {e}")
                if websocket in self._active_websockets:
                    self._active_websockets.remove(websocket)
 
    async def _handle_websocket_message(self, websocket: WebSocket, data: str) -> None:
        try:
            message = json.loads(data)
            if message.get("type") == "user.message":
                await self.event_bus.publish_async(
                    EventType.USER_MESSAGE,
                    {
                        "text": message.get("text", ""),
                        "user": message.get("user", "Alberto"),
                        "mode": message.get("mode", "normal"),
                    "source": "web",
                    "session_id": f"ws-{id(websocket)}",
                    "timestamp": datetime.now().isoformat()
                },
                source="web_server"
            )
        except json.JSONDecodeError:
            self.logger.error(f"❌ JSON inválido: {data[:100]}")
        except Exception as e:
            self.logger.error(f"❌ Erro processando WS: {e}")
 
    async def _on_response(self, event: Event) -> None:
        await self._broadcast({
            "type": "assistant.response",
            "text": event.data.get("text", ""),
            "session_id": event.data.get("session_id"),
            "timestamp": datetime.now().isoformat()
        })
 
    async def _on_processing_start(self, event: Event) -> None:
        await self._broadcast({"type": "processing.start"})
 
    async def _on_processing_end(self, event: Event) -> None:
        await self._broadcast({"type": "processing.end"})
 
    async def _on_pipeline_status(self, event: Event) -> None:
        await self._broadcast({
            "type": "pipeline.status",
            "step": event.data.get("step"),
            "timestamp": datetime.now().isoformat()
        })
 
    async def _on_error(self, event: Event) -> None:
        await self._broadcast({
            "type": "error",
            "message": event.data.get("error", "Erro desconhecido"),
            "timestamp": datetime.now().isoformat()
        })
 
    async def _on_reminder(self, event: Event) -> None:
        await self._broadcast({
            "type": "assistant.response",
            "text": f"🔔 {event.data.get('title', 'Lembrete')}\n{event.data.get('description', '')}",
            "user": "EVA",
            "metadata": {"type": "reminder"},
            "timestamp": datetime.now().isoformat()
        })
 
    async def _broadcast(self, message: Dict[str, Any]) -> None:
        if not self._active_websockets:
            return
        data = json.dumps(message)
        disconnected = []
        for ws in list(self._active_websockets):
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self._active_websockets:
                self._active_websockets.remove(ws)
 
    async def initialize(self) -> None:
        async with self._lifecycle_lock:
            if self._initialized:
                return
            self._subscribe_network_alerts()
            self._subscribe_web_events()
            self._initialized = True
            self.logger.info("WebServer: inicializado")
 
    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._running:
                return
            host = self.config.get("network.api_host", "0.0.0.0")
            port = self.config.get("network.api_port", 8000)
            server = uvicorn.Server(uvicorn.Config(self.app, host=host, port=port, log_level="warning"))
            self._server = server
            self._server_task = asyncio.create_task(server.serve())
            self._running = True
            self._server_port = port
            self.logger.info(f"WebServer: HTTP iniciado em http://{host}:{port}")
 
    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            self._stop_network_alerts()
            self._unsubscribe_web_events()
            await self._stop_http()
            self._initialized = False
            self.logger.info("WebServer: desligado")
 
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "websockets": len(self._active_websockets),
            "initialized": self._initialized,
            "port": self._server_port
        }
