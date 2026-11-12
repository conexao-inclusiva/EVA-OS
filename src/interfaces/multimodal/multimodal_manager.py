"""Gerenciador multimodal da EVA."""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from src.kernel.events import EventBus


class MultimodalManager:
    """
    Integra voz, visão e texto em uma interface unificada.
    """
    
    __plugin_name__ = "multimodal_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador multimodal da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["interface", "multimodal"]
    __plugin_capabilities__ = ["multimodal", "integration"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._voice_manager = None
        self._vision_manager = None
        self._running = False
    
    async def initialize(self) -> None:
        """Inicializa o MultimodalManager."""
        self.logger.info("MultimodalManager inicializando...")
        
        # Tenta obter voice manager
        try:
            from src.core.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            self._voice_manager = registry.get("voice_manager")
            self._vision_manager = registry.get("vision_manager")
        except:
            self.logger.warning("Voice/Vision managers não disponíveis")
        
        self._running = True
        self.logger.info("MultimodalManager inicializado")
    
    async def start(self) -> None:
        """Inicia o MultimodalManager."""
        self.logger.info("MultimodalManager iniciando...")
        self.logger.info("MultimodalManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o MultimodalManager."""
        self.logger.info("MultimodalManager desligando...")
        self._running = False
        self.logger.info("MultimodalManager desligado")
    
    # ===== COMANDOS MULTIMODAIS =====
    
    async def process_voice_command(self, text: str) -> Dict[str, Any]:
        """
        Processa um comando de voz.
        
        Args:
            text: Texto transcrito
            
        Returns:
            Resultado do processamento
        """
        self.logger.debug(f"Comando de voz: {text[:50]}...")
        
        # Publica como mensagem de usuário
        await self.event_bus.publish_async(
            "user.message",
            {
                "text": text,
                "source": "voice",
                "timestamp": datetime.now().isoformat()
            },
            source="multimodal_manager"
        )
        
        return {
            "processed": True,
            "text": text,
            "source": "voice",
            "timestamp": datetime.now().isoformat()
        }
    
    async def process_visual_input(self, image_path: str) -> Dict[str, Any]:
        """
        Processa uma entrada visual.
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            Resultado do processamento
        """
        self.logger.debug(f"Entrada visual: {image_path}")
        
        if self._vision_manager:
            # Detecta objetos
            objects = await self._vision_manager.detect_objects(image_path)
            
            # Reconhece faces
            faces = await self._vision_manager.recognize_faces(image_path)
            
            return {
                "processed": True,
                "objects": [{"label": o.label, "confidence": o.confidence} for o in objects],
                "faces": len(faces),
                "source": "vision",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "processed": False,
            "error": "Vision Manager não disponível",
            "timestamp": datetime.now().isoformat()
        }
    
    async def process_multimodal_input(self, text: str = None, 
                                      image_path: str = None) -> Dict[str, Any]:
        """
        Processa entrada multimodal.
        
        Args:
            text: Texto opcional
            image_path: Imagem opcional
            
        Returns:
            Resultado combinado
        """
        result = {
            "processed": True,
            "sources": [],
            "timestamp": datetime.now().isoformat()
        }
        
        if text:
            text_result = await self.process_voice_command(text)
            result["text"] = text_result
            result["sources"].append("voice")
        
        if image_path:
            vision_result = await self.process_visual_input(image_path)
            result["vision"] = vision_result
            result["sources"].append("vision")
        
        # Publica evento multimodal
        await self.event_bus.publish_async(
            "multimodal.input",
            result,
            source="multimodal_manager"
        )
        
        return result
    
    async def health_check(self) -> dict:
        """Health check do MultimodalManager."""
        return {
            "status": "running" if self._running else "stopped",
            "voice_available": self._voice_manager is not None,
            "vision_available": self._vision_manager is not None
        }