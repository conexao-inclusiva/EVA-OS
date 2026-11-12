"""API FastAPI da EVA."""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import uvicorn
import asyncio
import threading

from src.interfaces.api.routes import system, context, memory, knowledge, planner, agents, tools
from src.interfaces.api.websocket.ws_manager import WebSocketManager


# ===== MODELOS =====

class MessageRequest(BaseModel):
    """Requisição de mensagem."""
    text: str
    user: Optional[str] = "admin"
    context: Optional[Dict[str, Any]] = {}


class MessageResponse(BaseModel):
    """Resposta de mensagem."""
    text: str
    timestamp: str
    source: str


class StatusResponse(BaseModel):
    """Resposta de status."""
    status: str
    version: str
    uptime: float
    timestamp: str


# ===== API APP =====

class APIApp:
    """
    API FastAPI da EVA.
    """
    
    __plugin_name__ = "api"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "API REST da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["interface", "api"]
    __plugin_capabilities__ = ["api", "rest"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self.app = FastAPI(
            title="EVA OS API",
            description="API da EVA - Evolutionary Virtual Assistant",
            version="1.0.0"
        )
        
        self.ws_manager = WebSocketManager()
        self._running = False
        self._server_task: Optional[asyncio.Task] = None
        
        self._setup_middleware()
        self._setup_routes()
        self._setup_websocket()
    
    def _setup_middleware(self) -> None:
        """Configura middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self) -> None:
        """Configura rotas."""
        # Rotas principais
        @self.app.get("/")
        async def root():
            return {
                "name": "EVA OS API",
                "version": "1.0.0",
                "status": "running",
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.post("/message", response_model=MessageResponse)
        async def send_message(request: MessageRequest):
            """Envia uma mensagem para a EVA."""
            await self.event_bus.publish_async(
                "user.message",
                {
                    "text": request.text,
                    "source": "api",
                    "user": request.user,
                    "context": request.context,
                    "timestamp": datetime.now().isoformat()
                },
                source="api"
            )
            
            return MessageResponse(
                text="Mensagem recebida. Aguarde processamento.",
                timestamp=datetime.now().isoformat(),
                source="api"
            )
        
        @self.app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Obtém status do sistema."""
            # TODO: Obter status real
            return StatusResponse(
                status="running",
                version="1.0.0",
                uptime=0.0,
                timestamp=datetime.now().isoformat()
            )
        
        # Registra rotas dos módulos
        self.app.include_router(system.router, prefix="/api/system", tags=["system"])
        self.app.include_router(context.router, prefix="/api/context", tags=["context"])
        self.app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
        self.app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
        self.app.include_router(planner.router, prefix="/api/planner", tags=["planner"])
        self.app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
        self.app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    
    def _setup_websocket(self) -> None:
        """Configura WebSocket."""
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            
            try:
                while True:
                    data = await websocket.receive_text()
                    await self.ws_manager.handle_message(websocket, data)
            except WebSocketDisconnect:
                await self.ws_manager.disconnect(websocket)
    
    async def initialize(self) -> None:
        """Inicializa a API."""
        self.logger.info("API inicializando...")
        self._running = True
        self.logger.info("API inicializada")
    
    async def start(self) -> None:
        """Inicia a API."""
        self.logger.info("API iniciando...")
        
        host = self.config.get("network.api_host", "0.0.0.0")
        port = self.config.get("network.api_port", 8000)
        
        # Inicia o servidor em background
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        # Executa em thread separada
        def run_server():
            asyncio.run(server.serve())
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        self.logger.info(f"API iniciada em http://{host}:{port}")
        self.logger.info(f"Documentação: http://{host}:{port}/docs")
    
    async def shutdown(self) -> None:
        """Desliga a API."""
        self.logger.info("API desligando...")
        self._running = False
        self.logger.info("API desligada")
    
    async def health_check(self) -> dict:
        """Health check da API."""
        return {
            "status": "running" if self._running else "stopped",
            "websocket_connections": len(self.ws_manager.active_connections)
        }