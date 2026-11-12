"""Servidor Web para a EVA OS."""

import asyncio
import json
from typing import Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
from fastapi import Request


from contextlib import contextmanager


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
        self._server_error = None
        self._web_events_subscribed = False
        self._web_listener_bindings = (
            (EventType.ASSISTANT_RESPONSE, self._on_response),
            (EventType.PROCESSING_START, self._on_processing_start),
            (EventType.PROCESSING_END, self._on_processing_end),
            (EventType.COGNITIVE_ERROR, self._on_error),
            ("reminder.notification", self._on_reminder),
        )
        self._setup_routes()
        self._setup_websocket()
        self._setup_static()
        self._setup_network_alerts()
        self._subscribe_web_events()
        self.logger.info("WebServer: construido; HTTP ainda nao iniciado")

    

    # Canal de leitura de alertas; chave nao representa identidade familiar.
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
        self.event_bus.unsubscribe("security.network.alert", self._on_network_alert)
        self.event_bus.unsubscribe("security.network.recovered", self._on_network_alert)

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
        # Nao repassa mensagens arbitrarias, IPs, credenciais ou contexto familiar.
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

        # HTTP somente no proprio computador; acesso remoto exige HTTPS.
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
            self.event_bus.unsubscribe(name, callback)
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
        
        @self.app.get("/health")
        async def health():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}
        
        @self.app.post("/message")
        async def message(request: MessageRequest):
            await self.event_bus.publish_async(
                EventType.USER_MESSAGE,
                {
                    "text": request.text,
                    "user": request.user,
                    "mode": request.mode,
                    "source": "web",
                    "session_id": request.session_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="web_server"
            )
            return {"status": "received", "timestamp": datetime.now().isoformat()}
        
        @self.app.get("/status")
        async def status():
            return {
                "status": "running",
                "websockets": len(self._active_websockets),
                "timestamp": datetime.now().isoformat()
            }
    
    def _setup_websocket(self) -> None:
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._active_websockets.add(websocket)
            self.logger.info(f"🔌 WebSocket conectado: {len(self._active_websockets)}")
            
            try:
                while True:
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                if websocket in self._active_websockets:
                    self._active_websockets.remove(websocket)
                self.logger.info(f"🔌 WebSocket desconectado: {len(self._active_websockets)}")
            except Exception as e:
                self.logger.error(f"❌ Erro no WebSocket: {e}")
                if websocket in self._active_websockets:
                    self._active_websockets.remove(websocket)
    
    async def _handle_websocket_message(self, websocket: WebSocket, data: str) -> None:
        try:
            message = json.loads(data)
            
            if message.get("type") == "user.message":
                text = message.get("text", "")
                user = message.get("user", "Alberto")
                mode = message.get("mode", "normal")
                session_id = f"ws-{id(websocket)}"
                
                await self.event_bus.publish_async(
                    EventType.USER_MESSAGE,
                    {
                        "text": text,
                        "user": user,
                        "mode": mode,
                        "source": "web",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat()
                    },
                    source="web_server"
                )
            elif message.get("type") == "mode.change":
                mode = message.get("mode", "normal")
                self.logger.info(f"📱 Modo alterado: {mode}")
            else:
                self.logger.warning(f"⚠️ Tipo de mensagem desconhecido: {message.get('type')}")
        except json.JSONDecodeError:
            self.logger.error(f"❌ JSON inválido: {data}")
        except Exception as e:
            self.logger.error(f"❌ Erro ao processar mensagem: {e}")
    
    # ===== EVENTBUS LISTENERS =====
    
    async def _on_response(self, event: Event) -> None:
        await self._broadcast({
            "type": "assistant.response",
            "text": event.data.get("text", ""),
            "user": event.data.get("user", "EVA"),
            "metadata": event.data.get("metadata", {}),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _on_processing_start(self, event: Event) -> None:
        await self._broadcast({"type": "processing.start"})
    
    async def _on_processing_end(self, event: Event) -> None:
        await self._broadcast({"type": "processing.end"})
    
    async def _on_error(self, event: Event) -> None:
        await self._broadcast({
            "type": "error",
            "message": event.data.get("error", "Erro desconhecido")
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
        disconnected = set()
        
        for ws in self._active_websockets:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.add(ws)
        
        for ws in disconnected:
            if ws in self._active_websockets:
                self._active_websockets.remove(ws)
    
    # ===== SERVIDOR =====
    
    async def initialize(self) -> None:
        async with self._lifecycle_lock:
            if self._initialized:
                return
            self._subscribe_network_alerts()
            self._subscribe_web_events()
            self._shutdown_in_progress = False
            self._initialized = True
            self.logger.info("WebServer: inicializado; aguardando start")

    
    async def start(self) -> None:
        async with self._lifecycle_lock:
            if not self._initialized or self._shutdown_in_progress:
                raise RuntimeError("WebServer deve ser inicializado antes de start")
            if self._server_task is not None and not self._server_task.done():
                if self._running:
                    return
                raise RuntimeError("WebServer possui tarefa HTTP em transicao")

            host = self.config.get("network.api_host", "0.0.0.0")
            port = self.config.get("network.api_port", 8000)
            if not isinstance(host, str) or not host or host != host.strip():
                raise ValueError("Host HTTP invalido")
            if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
                raise ValueError("Porta HTTP invalida")
            if not hasattr(uvicorn.Server, "capture_signals"):
                raise RuntimeError("Interface de sinais do Uvicorn nao suportada")

            class ManagedServer(uvicorn.Server):
                @contextmanager
                def capture_signals(self):
                    # O processo principal da EVA controla SIGINT/SIGTERM.
                    yield

            server = ManagedServer(uvicorn.Config(
                self.app, host=host, port=port,
                log_level="warning", access_log=False,
                timeout_graceful_shutdown=3,
            ))
            self._server = server
            self._server_error = None

            async def run_http():
                try:
                    await server.serve()
                except asyncio.CancelledError:
                    raise
                except BaseException as error:
                    # Falhas de bind podem chegar como SystemExit pelo Uvicorn.
                    self._server_error = type(error).__name__
                    self.logger.error(
                        "WebServer: HTTP encerrou com %s", self._server_error
                    )
                finally:
                    self._running = False

            task = asyncio.create_task(run_http(), name="eva.web.http")
            self._server_task = task
            try:
                deadline = asyncio.get_running_loop().time() + 10
                while not server.started:
                    if task.done():
                        raise RuntimeError("Servidor HTTP nao iniciou")
                    if asyncio.get_running_loop().time() >= deadline:
                        raise TimeoutError("Timeout ao iniciar servidor HTTP")
                    await asyncio.sleep(0.025)
                if task.done() or server.should_exit:
                    raise RuntimeError("Servidor HTTP encerrou durante o inicio")
                sockets = [
                    sock
                    for listener in getattr(server, "servers", [])
                    for sock in (listener.sockets or ())
                ]
                if not sockets:
                    raise RuntimeError("Servidor HTTP sem socket de escuta")
                self._server_port = sockets[0].getsockname()[1]
                self._running = True
                self.logger.info(
                    "WebServer: HTTP iniciado em %s:%s", host, self._server_port
                )
            except BaseException:
                await self._stop_http()
                raise

    
    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            if self._shutdown_in_progress and self._server_task is None:
                return
            self._shutdown_in_progress = True
            self._initialized = False
            self._running = False
            self._stop_network_alerts()
            self._unsubscribe_web_events()

            async def close_socket(ws):
                try:
                    await asyncio.wait_for(ws.close(code=1001), timeout=2)
                except Exception:
                    pass

            try:
                await asyncio.gather(
                    *(close_socket(ws) for ws in list(self._active_websockets))
                )
            finally:
                self._active_websockets.clear()
                await self._stop_http()
            self.logger.info("WebServer: HTTP e WebSockets encerrados")

    
    async def health_check(self) -> dict:
        http_running = (
            self._running
            and self._server is not None
            and self._server.started
            and self._server_task is not None
            and not self._server_task.done()
        )
        status = "stopped"
        if http_running:
            status = "running"
        elif self._initialized:
            status = "failed" if self._server_error else "initialized"
        return {
            "status": status,
            "http_running": bool(http_running),
            "websockets": len(self._active_websockets),
            "startup_error": self._server_error,
        }

