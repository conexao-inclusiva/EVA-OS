"""Gerenciador de Voz da EVA - STT (Whisper) + TTS (gTTS)."""

import asyncio
import os
import tempfile
import wave
import numpy as np
import re
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
import subprocess

from src.kernel.events import EventBus


class VoiceManager:
    """
    Gerenciador de Voz da EVA.
    """
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._stt_model = None
        self._running = False
        self._listening = False
        self._listen_task: Optional[asyncio.Task] = None
        self._continuous_mode = False
        
        self._wake_word = "eva"
        self._sample_rate = 16000
        self._silence_threshold = 300
        self._silence_duration = 1.5
        self._min_speech_duration = 0.5
        
        self.logger.info("🎤 [VoiceManager] Inicializado")
    
    async def initialize(self) -> None:
        self.logger.info("🎤 [VoiceManager] Inicializando...")
        self._running = True
        await self._load_stt()
        self.logger.info(f"🎤 [VoiceManager] Inicializado (STT: {self._stt_model is not None})")
    
    async def _load_stt(self) -> None:
        try:
            import whisper
            model_name = self.config.get("voice.stt_model", "base")
            self._stt_model = whisper.load_model(model_name)
            self.logger.info(f"🎤 [STT] Whisper carregado: {model_name}")
        except ImportError:
            self.logger.warning("🎤 [STT] Whisper não disponível")
        except Exception as e:
            self.logger.error(f"🎤 [STT] Erro: {e}")
    
    async def speech_to_text(self, audio_path: Path) -> Optional[str]:
        if not self._stt_model:
            return None
        try:
            result = self._stt_model.transcribe(str(audio_path), language="pt")
            text = result.get("text", "").strip()
            if text:
                self.logger.info(f"🎤 [STT] Transcrito: '{text}'")
                return text
            return None
        except Exception as e:
            self.logger.error(f"🎤 [STT] Erro: {e}")
            return None
    
    def _remove_emojis(self, text: str) -> str:
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF"
            "\u2700-\u27BF"
            "\uFE00-\uFE0F"
            "]+",
            flags=re.UNICODE
        )
        clean = emoji_pattern.sub('', text)
        clean = re.sub(r'[✦▶️⏸️🧵🔔📰💡]', '', clean)
        clean = re.sub(r'[""``\']', '', clean)
        clean = re.sub(r'[=]{3,}', ' ', clean)
        clean = re.sub(r'[_-]{3,}', ' ', clean)
        clean = re.sub(r'http[s]?://\S+', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    async def text_to_speech(self, text: str, output_path: Optional[Path] = None) -> Optional[Path]:
        try:
            from gtts import gTTS
            clean_text = self._remove_emojis(text)
            if output_path is None:
                output_path = Path(tempfile.gettempdir()) / f"eva_tts_{datetime.now().timestamp()}.mp3"
            tts = gTTS(text=clean_text, lang='pt-br', slow=False)
            tts.save(str(output_path))
            self.logger.info(f"🎤 [TTS] Áudio gerado: {output_path}")
            return output_path
        except ImportError:
            self.logger.warning("🎤 [TTS] gTTS não disponível")
            return None
        except Exception as e:
            self.logger.error(f"🎤 [TTS] Erro: {e}")
            return None
    
    async def start_listening(self, callback: Optional[Callable] = None) -> None:
        if self._listening:
            return
        self._listening = True
        self._continuous_mode = False
        self._listen_task = asyncio.create_task(self._continuous_listen(callback))
        self.logger.info("🎤 [ESCUTA] Escuta ativa iniciada")
    
    async def stop_listening(self) -> None:
        self._listening = False
        self._continuous_mode = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self.logger.info("🎤 [ESCUTA] Escuta ativa parada")
    
    async def _continuous_listen(self, callback: Optional[Callable]) -> None:
        self.logger.info("🎤 [ESCUTA] Aguardando 'EVA...'")
        
        try:
            import sounddevice as sd
            import numpy as np
            
            chunk = 1024
            silent_chunks = 0
            max_silent_chunks = int(self._sample_rate / chunk * self._silence_duration)
            recording = False
            frames = []
            
            stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype=np.int16,
                blocksize=chunk
            )
            stream.start()
            
            while self._listening:
                data, _ = stream.read(chunk)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                if volume > self._silence_threshold:
                    if not recording:
                        recording = True
                        frames = []
                        silent_chunks = 0
                        self.logger.debug("🎤 [ESCUTA] Fala detectada")
                    frames.append(data)
                    silent_chunks = 0
                elif recording:
                    frames.append(data)
                    silent_chunks += 1
                    
                    if silent_chunks > max_silent_chunks and len(frames) > int(self._sample_rate / chunk * self._min_speech_duration):
                        recording = False
                        self.logger.debug("🎤 [ESCUTA] Fala finalizada")
                        
                        temp_file = Path(tempfile.gettempdir()) / f"eva_speech_{datetime.now().timestamp()}.wav"
                        
                        with wave.open(str(temp_file), 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(self._sample_rate)
                            wf.writeframes(b''.join(frames))
                        
                        asyncio.create_task(self._process_audio(temp_file, callback))
                        frames = []
                
                await asyncio.sleep(0.01)
            
            stream.stop()
            stream.close()
            
        except ImportError:
            self.logger.warning("🎤 [ESCUTA] sounddevice não disponível")
            self._listening = False
        except Exception as e:
            self.logger.error(f"🎤 [ESCUTA] Erro: {e}")
            self._listening = False
    
    async def _process_audio(self, audio_path: Path, callback: Optional[Callable]) -> None:
        try:
            text = await self.speech_to_text(audio_path)
            
            if text:
                text_lower = text.lower()
                
                if self._wake_word in text_lower or self._continuous_mode:
                    clean_text = text_lower
                    if self._wake_word in clean_text:
                        clean_text = clean_text.replace(self._wake_word, "").strip()
                        self._continuous_mode = True
                        self.logger.info("🎤 [ESCUTA] Modo contínuo ativado")
                    
                    if clean_text in ["stop", "eva stop", "parar"]:
                        self._continuous_mode = False
                        self.logger.info("🎤 [ESCUTA] Modo contínuo desativado")
                        await self.say("Ok, parando.")
                        return
                    
                    if clean_text:
                        self.logger.info(f"🎤 [COMANDO] '{clean_text}'")
                        
                        await self.event_bus.publish_async(
                            "voice.command",
                            {
                                "text": clean_text,
                                "source": "voice",
                                "continuous": self._continuous_mode,
                                "timestamp": datetime.now().isoformat()
                            },
                            source="voice_manager"
                        )
                        
                        if callback:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(clean_text)
                            else:
                                callback(clean_text)
                else:
                    self.logger.debug(f"🎤 [ESCUTA] Ignorado: '{text}'")
            
            try:
                audio_path.unlink()
            except:
                pass
            
        except Exception as e:
            self.logger.error(f"🎤 [PROCESSAMENTO] Erro: {e}")
    
    # ===== FALLBACK TTS LOCAL WINDOWS SAPI =====
    async def _speak_with_windows_sapi(self, text: str) -> bool:
        """Fala localmente pelo Windows quando o gTTS online falhar."""
        try:
            import base64

            clean_text = self._remove_emojis(text).strip()
            if not clean_text:
                return False

            text_b64 = base64.b64encode(clean_text.encode("utf-8")).decode("ascii")
            ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$textBytes = [Convert]::FromBase64String('{text_b64}')
$speechText = [System.Text.Encoding]::UTF8.GetString($textBytes)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $ptVoice = @($synth.GetInstalledVoices() | Where-Object {{ $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'pt-BR' }})
    if ($ptVoice.Count -gt 0) {{
        $synth.SelectVoice($ptVoice[0].VoiceInfo.Name)
    }}
    [Console]::Out.WriteLine('VOICE=' + $synth.Voice.Name)
    $synth.Rate = 0
    $synth.Volume = 100
    $synth.Speak($speechText)
}} finally {{
    $synth.Dispose()
}}
"""
            encoded_script = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
            powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            if not powershell.exists():
                powershell = Path("powershell.exe")

            result = await asyncio.to_thread(
                subprocess.run,
                [str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                voice_name = next(
                    (line[6:] for line in result.stdout.splitlines() if line.startswith("VOICE=")),
                    None,
                )
                if voice_name:
                    self.logger.info(f"🎤 [TTS] Fallback local do Windows ativo: {voice_name}")
                else:
                    self.logger.info("🎤 [TTS] Fala local do Windows concluída")
                return True

            self.logger.error(f"🎤 [TTS] Fallback Windows falhou: {result.stderr[-500:]}")
        except Exception as e:
            self.logger.error(f"🎤 [TTS] Falha no fallback local do Windows: {e}")
        return False
    # ===== FALAR (CORRIGIDO - COM FFPLAY) =====
    
    async def say(self, text: str) -> bool:
        """Fala o texto usando ffplay (sem janela)."""
        clean_text = self._remove_emojis(text)
        self.logger.info(f"🎤 [FALAR] '{clean_text[:50]}...'")
        
        await self.event_bus.publish_async(
            "voice.speaking",
            {
                "text": text,
                "clean_text": clean_text,
                "timestamp": datetime.now().isoformat()
            },
            source="voice_manager"
        )
        
        audio_path = await self.text_to_speech(text)
        if not audio_path:
            self.logger.warning("🎤 [TTS] gTTS sem conexão; usando a voz local do Windows.")
            return await self._speak_with_windows_sapi(clean_text)
        
        if audio_path:
            try:
                # 🔥 SOLUÇÃO DEFINITIVA: ffplay com -nodisp (SEM JANELA)
                subprocess.Popen(
                    ['ffplay', '-nodisp', '-autoexit', str(audio_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                self.logger.info(f"🎤 [FALAR] Áudio tocando em segundo plano (ffplay): {audio_path}")
                
                async def delete_audio():
                    await asyncio.sleep(5)
                    try:
                        if audio_path.exists():
                            audio_path.unlink()
                    except:
                        pass
                
                asyncio.create_task(delete_audio())
                return True
                
            except FileNotFoundError:
                self.logger.warning("⚠️ ffplay não encontrado. Instale o FFmpeg.")
                # Fallback: tenta o player padrão (vai abrir janela)
                try:
                    os.startfile(str(audio_path))
                    return True
                except:
                    return False
            except Exception as e:
                self.logger.error(f"🎤 [FALAR] Erro ao tocar: {e}")
                return False
        return False
    
    async def shutdown(self) -> None:
        self.logger.info("🎤 [VoiceManager] Desligando...")
        self._running = False
        await self.stop_listening()
        self.logger.info("🎤 [VoiceManager] Desligado")
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "stt_available": self._stt_model is not None,
            "listening": self._listening,
            "continuous_mode": self._continuous_mode
        }