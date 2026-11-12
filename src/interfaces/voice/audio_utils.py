"""Utilitários de áudio (com fallbacks)."""

import wave
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime
import os


class AudioUtils:
    """
    Utilitários para manipulação de áudio.
    """
    
    _pyaudio_available = False
    _playsound_available = False
    _librosa_available = False
    _soundfile_available = False
    
    @classmethod
    def _check_imports(cls) -> None:
        """Verifica dependências disponíveis."""
        if not hasattr(cls, '_checked'):
            try:
                import pyaudio
                cls._pyaudio_available = True
            except:
                pass
            
            try:
                import playsound
                cls._playsound_available = True
            except:
                pass
            
            try:
                import librosa
                cls._librosa_available = True
            except:
                pass
            
            try:
                import soundfile
                cls._soundfile_available = True
            except:
                pass
            
            cls._checked = True
    
    @staticmethod
    def record_audio(duration: float, rate: int = 16000, channels: int = 1) -> Optional[Path]:
        """
        Grava áudio do microfone.
        """
        AudioUtils._check_imports()
        
        if not AudioUtils._pyaudio_available:
            print("[FALLBACK] PyAudio não disponível. Criando áudio simulado...")
            # Cria um arquivo de áudio simulado (silêncio)
            temp_file = Path(tempfile.gettempdir()) / f"eva_record_{datetime.now().timestamp()}.wav"
            with wave.open(str(temp_file), 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(b'\x00' * int(rate * duration * channels * 2))
            return temp_file
        
        try:
            import pyaudio
            import numpy as np
            
            chunk = 1024
            format = pyaudio.paInt16
            
            p = pyaudio.PyAudio()
            stream = p.open(format=format, channels=channels, rate=rate,
                          input=True, frames_per_buffer=chunk)
            
            frames = []
            
            for _ in range(0, int(rate / chunk * duration)):
                data = stream.read(chunk)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            temp_file = Path(tempfile.gettempdir()) / f"eva_record_{datetime.now().timestamp()}.wav"
            
            with wave.open(str(temp_file), 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(p.get_sample_size(format))
                wf.setframerate(rate)
                wf.writeframes(b''.join(frames))
            
            return temp_file
            
        except Exception as e:
            print(f"Erro ao gravar áudio: {e}")
            return None
    
    @staticmethod
    def play_audio(audio_path: Path) -> bool:
        """
        Reproduz um arquivo de áudio.
        """
        AudioUtils._check_imports()
        
        if not AudioUtils._playsound_available:
            print(f"[FALLBACK] Áudio salvo em: {audio_path}")
            return True
        
        try:
            import playsound
            playsound.playsound(str(audio_path))
            return True
        except Exception as e:
            print(f"Erro ao reproduzir áudio: {e}")
            return False
    
    @staticmethod
    def convert_to_wav(input_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Converte áudio para WAV.
        """
        AudioUtils._check_imports()
        
        if not AudioUtils._librosa_available or not AudioUtils._soundfile_available:
            print("[FALLBACK] Librosa/Soundfile não disponível. Copiando arquivo...")
            if output_path is None:
                output_path = Path(tempfile.gettempdir()) / f"eva_converted_{datetime.now().timestamp()}.wav"
            
            # Copia o arquivo
            import shutil
            shutil.copy(input_path, output_path)
            return output_path
        
        try:
            import librosa
            import soundfile as sf
            
            if output_path is None:
                output_path = Path(tempfile.gettempdir()) / f"eva_converted_{datetime.now().timestamp()}.wav"
            
            audio, sr = librosa.load(str(input_path), sr=16000)
            sf.write(str(output_path), audio, sr)
            
            return output_path
            
        except Exception as e:
            print(f"Erro na conversão: {e}")
            return None
    
    @staticmethod
    def get_audio_duration(audio_path: Path) -> float:
        """
        Obtém duração de um arquivo de áudio.
        """
        AudioUtils._check_imports()
        
        if AudioUtils._librosa_available:
            try:
                import librosa
                duration = librosa.get_duration(filename=str(audio_path))
                return duration
            except:
                pass
        
        try:
            import wave
            with wave.open(str(audio_path), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except:
            return 0.0