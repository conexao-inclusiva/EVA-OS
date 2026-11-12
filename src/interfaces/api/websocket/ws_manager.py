"""Gerenciador de WebSocket."""

from typing import Dict, Any, List, Set
from fastapi import WebSocket
import json
from datetime import datetime


class WebSocketManager:
    """
    Gerenciador de conexões WebSocket.
    """
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_data: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket) -> None:
        """Aceita uma conexão."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_data[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "messages_received": 0,
            "messages_sent": 0
        }
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove uma conexão."""
        self.active_connections.remove(websocket)
        if websocket in self.connection_data:
            del self.connection_data[websocket]
    
    async def handle_message(self, websocket: WebSocket, message: str) -> None:
        """Processa uma mensagem recebida."""
        try:
            data = json.loads(message)
            self.connection_data[websocket]["messages_received"] += 1
            
            # Echo
            response = {
                "type": "echo",
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.send_message(websocket, response)
            
        except json.JSONDecodeError:
            await self.send_message(websocket, {
                "type": "error",
                "message": "JSON inválido",
                "timestamp": datetime.now().isoformat()
            })
    
    async def send_message(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Envia uma mensagem."""
        try:
            await websocket.send_json(data)
            if websocket in self.connection_data:
                self.connection_data[websocket]["messages_sent"] += 1
        except Exception:
            pass
    
    async def broadcast(self, data: Dict[str, Any]) -> None:
        """Transmite uma mensagem para todas as conexões."""
        for connection in self.active_connections:
            await self.send_message(connection, data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas."""
        return {
            "active_connections": len(self.active_connections),
            "connections": [
                {
                    "connected_at": data.get("connected_at"),
                    "messages_received": data.get("messages_received", 0),
                    "messages_sent": data.get("messages_sent", 0)
                }
                for data in self.connection_data.values()
            ]
        }