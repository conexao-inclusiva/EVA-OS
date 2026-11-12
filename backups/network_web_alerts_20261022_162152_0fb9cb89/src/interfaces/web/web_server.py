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
        
        # Registra listeners
        self.event_bus.subscribe(EventType.ASSISTANT_RESPONSE, self._on_response)
        self.event_bus.subscribe(EventType.PROCESSING_START, self._on_processing_start)
        self.event_bus.subscribe(EventType.PROCESSING_END, self._on_processing_end)
        self.event_bus.subscribe(EventType.COGNITIVE_ERROR, self._on_error)
        self.event_bus.subscribe("reminder.notification", self._on_reminder)
        
        self.logger.info("🌐 [WebServer] Inicializado")
    
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