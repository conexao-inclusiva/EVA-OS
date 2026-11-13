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
        self._shutdown_in_progress = False
        
        self._setup_routes()
        self._setup_websocket()
        self._setup_static()
        self._setup_network_alerts()
        
        # Registra listeners
        self.event_bus.subscribe(EventType.ASSISTANT_RESPONSE, self._on_response)
        self.event_bus.subscribe(EventType.PROCESSING_START, self._on_processing_start)
        self.event_bus.subscribe(EventType.PROCESSING_END, self._on_processing_end)
        self.event_bus.subscribe(EventType.COGNITIVE_ERROR, self._on_error)
        self.event_bus.subscribe("reminder.notification", self._on_reminder)
        
        self.logger.info("🌐 [WebServer] Inicializado")
    

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
        self.logger.info("🌐 [WebServer] Inicializando...")
        self._subscribe_network_alerts()
        self._running = True
        self._shutdown_in_progress = False
        self.logger.info("🌐 [WebServer] Inicializado")
    
    async def start(self) -> None:
        self.logger.info("🌐 [WebServer] Iniciando...")
        
        host = self.config.get("network.api_host", "0.0.0.0")
        port = self.config.get("network.api_port", 8000)
        
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        
        def run_server():
            asyncio.run(server.serve())
        
        import threading
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        self.logger.info(f"🌐 [WebServer] Rodando em http://{host}:{port}")
        self.logger.info(f"📱 Interface: http://{host}:{port}")
    
    async def shutdown(self) -> None:
        self.logger.info("🌐 [WebServer] Desligando...")
        self._running = False
        self._shutdown_in_progress = True
        self._stop_network_alerts()
        
        for ws in list(self._active_websockets):
            try:
                await ws.close()
            except Exception:
                pass
        self._active_websockets.clear()
        
        self.logger.info("🌐 [WebServer] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "websockets": len(self._active_websockets)
        }