"""Gerenciador de voz da EVA (com fallbacks)."""

import asyncio
import os
import tempfile
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

from src.kernel.events import EventBus


class VoiceManager:
    """
    Gerenciador de voz da EVA.
    
    Responsabilidades:
    - Capturar áudio do microfone
    - Converter fala em texto (STT)
    - Converter texto em fala (TTS)
    - Gerenciar dispositivos de áudio
    """
    
    __plugin_name__ = "voice_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de voz da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["interface", "voice", "speech"]
    __plugin_capabilities__ = ["voice", "stt", "tts"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._stt = None
        self._stt_available = False
        self._tts = None
        self._tts_available = False
        self._running = False
        self._listening = False
        self._record_task: Optional[asyncio.Task] = None
        
        self._on_phrase_callback: Optional[Callable] = None
    
    async def initialize(self) -> None:
        """Inicializa o VoiceManager."""
        self.logger.info("VoiceManager inicializando...")
        
        # Inicializa STT (tenta carregar)
        await self._init_stt()
        
        # Inicializa TTS (tenta carregar)
        await self._init_tts()
        
        self._running = True
        self.logger.info(f"VoiceManager inicializado (STT: {self._stt_available}, TTS: {self._tts_available})")
    
    async def start(self) -> None:
        """Inicia o VoiceManager."""
        self.logger.info("VoiceManager iniciando...")
        self.logger.info("VoiceManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o VoiceManager."""
        self.logger.info("VoiceManager desligando...")
        self._running = False
        
        if self._record_task:
            self._record_task.cancel()
            try:
                await self._record_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("VoiceManager desligado")
    
    # ===== STT (Speech to Text) =====
    
    async def _init_stt(self) -> None:
        """Inicializa o STT com fallback."""
        try:
            import whisper
            model_name = self.config.get("voice.stt_model", "base")
            self._stt = whisper.load_model(model_name)
            self._stt_available = True
            self.logger.info(f"STT carregado: {model_name}")
        except ImportError:
            self.logger.warning("Whisper não disponível. STT desativado.")
            self._stt_available = False
        except Exception as e:
            self.logger.error(f"Erro ao carregar STT: {e}")
            self._stt_available = False
    
    async def speech_to_text(self, audio_path: Path) -> Optional[str]:
        """
        Converte áudio para texto.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            
        Returns:
            Texto transcrito ou None se falhar
        """
        if not self._stt_available:
            self.logger.warning("STT não disponível")
            return None
        
        try:
            result = self._stt.transcribe(str(audio_path))
            text = result.get("text", "").strip()
            if text:
                self.logger.debug(f"STT: {text[:50]}...")
                return text
            return None
        except Exception as e:
            self.logger.error(f"Erro no STT: {e}")
            return None
    
    # ===== TTS (Text to Speech) =====
    
    async def _init_tts(self) -> None:
        """Inicializa o TTS com fallback."""
        try:
            from TTS.api import TTS
            
            model_name = self.config.get("voice.tts_model", "tts_models/pt-br/fairseq/vits")
            self._tts = TTS(model_name)
            self._tts_available = True
            self.logger.info(f"TTS carregado: {model_name}")
        except ImportError:
            self.logger.warning("TTS não disponível. TTS desativado.")
            self._tts_available = False
        except Exception as e:
            self.logger.error(f"Erro ao carregar TTS: {e}")
            self._tts_available = False
    
    async def text_to_speech(self, text: str, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Converte texto para fala.
        
        Args:
            text: Texto a ser falado
            output_path: Caminho para salvar o áudio
            
        Returns:
            Caminho do arquivo de áudio ou None se falhar
        """
        if not self._tts_available:
            self.logger.warning("TTS não disponível")
            # Fallback: apenas log
            self.logger.info(f"[FALLBACK] TTS: {text[:100]}...")
            return None
        
        try:
            if output_path is None:
                output_path = Path(tempfile.gettempdir()) / f"eva_tts_{datetime.now().timestamp()}.wav"
            
            self._tts.tts_to_file(text=text, file_path=str(output_path))
            self.logger.debug(f"TTS gerado: {output_path}")
            return output_path
        except Exception as e:
            self.logger.error(f"Erro no TTS: {e}")
            return None
    
    # ===== GRAVAÇÃO (com fallback) =====
    
    async def start_listening(self, callback: Optional[Callable] = None) -> None:
        """
        Inicia escuta contínua do microfone.
        """
        if self._listening:
            return
        
        self._listening = True
        self._on_phrase_callback = callback
        
        try:
            self._record_task = asyncio.create_task(self._continuous_listen())
            self.logger.info("Escuta contínua iniciada")
        except Exception as e:
            self.logger.error(f"Erro ao iniciar escuta: {e}")
            self._listening = False
    
    async def stop_listening(self) -> None:
        """Para a escuta contínua."""
        self._listening = False
        
        if self._record_task:
            self._record_task.cancel()
            try:
                await self._record_task
            except asyncio.CancelledError:
                pass
            self._record_task = None
        
        self.logger.info("Escuta contínua parada")
    
    async def _continuous_listen(self) -> None:
        """Loop de escuta contínua (com fallback)."""
        try:
            import pyaudio
            import wave
            import numpy as np
            
            chunk = 1024
            format = pyaudio.paInt16
            channels = 1
            rate = 16000
            silence_threshold = 500
            silence_duration = 2.0
            
            p = pyaudio.PyAudio()
            stream = p.open(format=format, channels=channels, rate=rate,
                          input=True, frames_per_buffer=chunk)
            
            frames = []
            silent_frames = 0
            max_silent_frames = int(rate / chunk * silence_duration)
            recording = False
            
            self.logger.info("Microfone ativo. Aguardando fala...")
            
            while self._listening:
                data = stream.read(chunk, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                if volume > silence_threshold:
                    if not recording:
                        recording = True
                        frames = []
                        self.logger.debug("Início da fala detectado")
                    frames.append(data)
                    silent_frames = 0
                elif recording:
                    frames.append(data)
                    silent_frames += 1
                    
                    if silent_frames > max_silent_frames:
                        recording = False
                        self.logger.debug("Fim da fala detectado")
                        
                        temp_file = Path(tempfile.gettempdir()) / f"eva_speech_{datetime.now().timestamp()}.wav"
                        
                        with wave.open(str(temp_file), 'wb') as wf:
                            wf.setnchannels(channels)
                            wf.setsampwidth(p.get_sample_size(format))
                            wf.setframerate(rate)
                            wf.writeframes(b''.join(frames))
                        
                        asyncio.create_task(self._process_audio(temp_file))
                        frames = []
                
                await asyncio.sleep(0.01)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except ImportError:
            self.logger.warning("PyAudio não disponível. Escuta contínua desativada.")
            self._listening = False
            # Mantém rodando em modo sleep
            while self._listening:
                await asyncio.sleep(1)
                self.logger.debug("[FALLBACK] Escuta simulada...")
                
        except Exception as e:
            self.logger.error(f"Erro na escuta contínua: {e}")
            self._listening = False
    
    async def _process_audio(self, audio_path: Path) -> None:
        """Processa áudio capturado."""
        try:
            text = await self.speech_to_text(audio_path)
            
            if text:
                await self.event_bus.publish_async(
                    "voice.input",
                    {
                        "text": text,
                        "source": "voice",
                        "timestamp": datetime.now().isoformat()
                    },
                    source="voice_manager"
                )
                
                if self._on_phrase_callback:
                    if asyncio.iscoroutinefunction(self._on_phrase_callback):
                        await self._on_phrase_callback(text)
                    else:
                        self._on_phrase_callback(text)
            
            try:
                audio_path.unlink()
            except:
                pass
            
        except Exception as e:
            self.logger.error(f"Erro ao processar áudio: {e}")
    
    # ===== MÉTODOS PÚBLICOS =====
    
    async def say(self, text: str) -> bool:
        """
        Faz a EVA falar um texto.
        """
        if not self._tts_available:
            self.logger.info(f"[FALLBACK] EVA diria: {text[:100]}...")
            return True
        
        audio_path = await self.text_to_speech(text)
        
        if audio_path:
            try:
                import playsound
                playsound.playsound(str(audio_path))
                try:
                    audio_path.unlink()
                except:
                    pass
                return True
            except ImportError:
                self.logger.warning("playsound não disponível. Áudio salvo em: {audio_path}")
                return True
            except Exception as e:
                self.logger.error(f"Erro ao reproduzir áudio: {e}")
                return False
        
        return False
    
    async def health_check(self) -> dict:
        """Health check do VoiceManager."""
        return {
            "status": "running" if self._running else "stopped",
            "stt_available": self._stt_available,
            "tts_available": self._tts_available,
            "listening": self._listening
        }