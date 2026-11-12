"""Módulo de Interfaces da EVA OS."""

from src.interfaces.interface_manager import InterfaceManager
from src.interfaces.cli.cli import CLI
from src.interfaces.api.app import APIApp
from src.interfaces.web.web_server import WebServer  # <-- ADICIONADO

# Voz
from src.interfaces.voice.voice_manager import VoiceManager
from src.interfaces.voice.audio_utils import AudioUtils

# Visão
from src.interfaces.vision.vision_manager import VisionManager

# Multimodal
from src.interfaces.multimodal.multimodal_manager import MultimodalManager

__all__ = [
    "InterfaceManager",
    "CLI",
    "APIApp",
    "WebServer",  # <-- ADICIONADO
    "VoiceManager",
    "AudioUtils",
    "VisionManager",
    "MultimodalManager"
]