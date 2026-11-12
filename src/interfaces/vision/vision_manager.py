"""Gerenciador de visão da EVA (com fallbacks)."""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass

from src.kernel.events import EventBus


@dataclass
class DetectedObject:
    """Objeto detectado."""
    label: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


class VisionManager:
    """
    Gerenciador de visão da EVA.
    
    Responsabilidades:
    - Capturar imagens de câmeras
    - Detectar objetos (YOLO)
    - Reconhecer faces
    - Processar imagens
    """
    
    __plugin_name__ = "vision_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de visão da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["interface", "vision", "camera"]
    __plugin_capabilities__ = ["vision", "object_detection", "face_recognition"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self._running = False
        self._cameras: Dict[str, Any] = {}
        self._camera_tasks: Dict[str, asyncio.Task] = {}
        
        self._detector = None
        self._detector_available = False
        self._face_recognizer = None
        self._face_available = False
        self._cv2_available = False
        
        self._on_detection_callback: Optional[Callable] = None
    
    async def initialize(self) -> None:
        """Inicializa o VisionManager."""
        self.logger.info("VisionManager inicializando...")
        
        # Tenta carregar OpenCV
        try:
            import cv2
            self._cv2 = cv2
            self._cv2_available = True
            self.logger.info("OpenCV disponível")
        except ImportError:
            self.logger.warning("OpenCV não disponível")
            self._cv2_available = False
        
        # Inicializa detector
        await self._init_detector()
        
        # Inicializa reconhecimento facial
        await self._init_face_recognizer()
        
        self._running = True
        self.logger.info(f"VisionManager inicializado (Detector: {self._detector_available}, Face: {self._face_available})")
    
    async def start(self) -> None:
        """Inicia o VisionManager."""
        self.logger.info("VisionManager iniciando...")
        self.logger.info("VisionManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o VisionManager."""
        self.logger.info("VisionManager desligando...")
        self._running = False
        
        for camera_id in list(self._camera_tasks.keys()):
            await self.stop_camera(camera_id)
        
        self.logger.info("VisionManager desligado")
    
    # ===== DETECTOR (YOLO) =====
    
    async def _init_detector(self) -> None:
        """Inicializa o detector de objetos."""
        try:
            from ultralytics import YOLO
            model_name = self.config.get("vision.detection_model", "yolov8n.pt")
            self._detector = YOLO(model_name)
            self._detector_available = True
            self.logger.info(f"Detector carregado: {model_name}")
        except ImportError:
            self.logger.warning("Ultralytics/YOLO não disponível. Detecção desativada.")
            self._detector_available = False
        except Exception as e:
            self.logger.error(f"Erro ao carregar detector: {e}")
            self._detector_available = False
    
    async def _init_face_recognizer(self) -> None:
        """Inicializa o reconhecimento facial."""
        try:
            import face_recognition
            self._face_recognizer = face_recognition
            self._face_available = True
            self.logger.info("Reconhecimento facial disponível")
        except ImportError:
            self.logger.warning("face_recognition não disponível. Reconhecimento facial desativado.")
            self._face_available = False
    
    async def detect_objects(self, image_path: Path) -> List[DetectedObject]:
        """
        Detecta objetos em uma imagem.
        """
        if not self._detector_available:
            self.logger.warning("Detector não disponível")
            return []
        
        try:
            results = self._detector(str(image_path))
            
            objects = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        label = self._detector.names[cls]
                        
                        objects.append(DetectedObject(
                            label=label,
                            confidence=conf,
                            x=int(x1),
                            y=int(y1),
                            width=int(x2 - x1),
                            height=int(y2 - y1)
                        ))
            
            return objects
        except Exception as e:
            self.logger.error(f"Erro na detecção: {e}")
            return []
    
    async def recognize_faces(self, image_path: Path) -> List[Dict[str, Any]]:
        """
        Reconhece faces em uma imagem.
        """
        if not self._face_available:
            self.logger.warning("Reconhecimento facial não disponível")
            return []
        
        try:
            import face_recognition
            
            image = face_recognition.load_image_file(str(image_path))
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            results = []
            for location, encoding in zip(face_locations, face_encodings):
                results.append({
                    "location": {
                        "top": location[0],
                        "right": location[1],
                        "bottom": location[2],
                        "left": location[3]
                    },
                    "encoding": encoding.tolist() if hasattr(encoding, 'tolist') else None
                })
            
            return results
        except Exception as e:
            self.logger.error(f"Erro no reconhecimento facial: {e}")
            return []
    
    # ===== CÂMERAS (com fallback) =====
    
    async def start_camera(self, camera_id: str, source: int = 0) -> bool:
        """
        Inicia uma câmera.
        """
        if not self._cv2_available:
            self.logger.warning("OpenCV não disponível. Câmera simulada.")
            return True
        
        if camera_id in self._camera_tasks:
            self.logger.warning(f"Câmera {camera_id} já está rodando")
            return False
        
        try:
            cap = self._cv2.VideoCapture(source)
            if not cap.isOpened():
                self.logger.error(f"Não foi possível abrir câmera {camera_id}")
                return False
            
            self._cameras[camera_id] = cap
            self._camera_tasks[camera_id] = asyncio.create_task(
                self._camera_loop(camera_id)
            )
            
            self.logger.info(f"Câmera {camera_id} iniciada (fonte: {source})")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao iniciar câmera {camera_id}: {e}")
            return False
    
    async def stop_camera(self, camera_id: str) -> bool:
        """Para uma câmera."""
        if camera_id not in self._camera_tasks:
            return False
        
        task = self._camera_tasks.pop(camera_id)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        if camera_id in self._cameras:
            cap = self._cameras.pop(camera_id)
            if self._cv2_available:
                cap.release()
        
        self.logger.info(f"Câmera {camera_id} parada")
        return True
    
    async def _camera_loop(self, camera_id: str) -> None:
        """Loop de captura de uma câmera."""
        if not self._cv2_available:
            # Fallback: loop simulado
            while self._running and camera_id in self._cameras:
                await asyncio.sleep(1)
                self.logger.debug(f"[FALLBACK] Câmera {camera_id} simulada...")
            return
        
        cap = self._cameras.get(camera_id)
        if not cap:
            return
        
        frame_interval = 1.0 / self.config.get("vision.fps", 15)
        
        while self._running and camera_id in self._cameras:
            try:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.1)
                    continue
                
                await self._process_frame(camera_id, frame)
                await asyncio.sleep(frame_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro na câmera {camera_id}: {e}")
                await asyncio.sleep(1)
    
    async def _process_frame(self, camera_id: str, frame: Any) -> None:
        """Processa um frame da câmera."""
        if not self._detector_available:
            return
        
        try:
            results = self._detector(frame)
            
            objects = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        label = self._detector.names[cls]
                        
                        objects.append({
                            "label": label,
                            "confidence": conf,
                            "x": int(x1),
                            "y": int(y1),
                            "width": int(x2 - x1),
                            "height": int(y2 - y1)
                        })
            
            if objects:
                await self.event_bus.publish_async(
                    "vision.detection",
                    {
                        "camera": camera_id,
                        "objects": objects,
                        "timestamp": datetime.now().isoformat()
                    },
                    source="vision_manager"
                )
                
                if self._on_detection_callback:
                    if asyncio.iscoroutinefunction(self._on_detection_callback):
                        await self._on_detection_callback(camera_id, objects)
                    else:
                        self._on_detection_callback(camera_id, objects)
                        
        except Exception as e:
            pass
    
    # ===== MÉTODOS PÚBLICOS =====
    
    async def capture_frame(self, camera_id: str) -> Optional[Any]:
        """Captura um frame de uma câmera."""
        if not self._cv2_available:
            return None
        
        cap = self._cameras.get(camera_id)
        if not cap:
            return None
        
        ret, frame = cap.read()
        if not ret:
            return None
        
        return frame
    
    async def save_frame(self, camera_id: str, output_path: Path) -> bool:
        """Salva um frame de uma câmera."""
        if not self._cv2_available:
            return False
        
        frame = await self.capture_frame(camera_id)
        if frame is None:
            return False
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._cv2.imwrite(str(output_path), frame)
        return True
    
    def set_detection_callback(self, callback: Callable) -> None:
        """Define callback para detecções."""
        self._on_detection_callback = callback
    
    async def health_check(self) -> dict:
        """Health check do VisionManager."""
        return {
            "status": "running" if self._running else "stopped",
            "cv2_available": self._cv2_available,
            "detector_available": self._detector_available,
            "face_recognizer_available": self._face_available,
            "active_cameras": list(self._cameras.keys()),
            "camera_count": len(self._cameras)
        }