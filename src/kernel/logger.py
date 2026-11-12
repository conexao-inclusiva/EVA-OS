"""Sistema de logging do Kernel."""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler


class KernelLogger:
    """
    Muito mais que logs.
    Cada evento da EVA será registrado.
    No futuro teremos auditoria completa.
    """
    
    def __init__(self, config):
        self.config = config
        
        # Configuração
        self.log_level = config.get("system.log_level", "INFO")
        self.log_file = config.get("system.log_file", "./data/logs/eva.log")
        
        # Cria logger
        self._logger = logging.getLogger("EVA")
        self._logger.setLevel(getattr(logging, self.log_level))
        
        # Remove handlers existentes
        self._logger.handlers.clear()
        
        # Configura handlers
        self._setup_console_handler()
        self._setup_file_handler()
        
        # Para auditoria
        self._audit_log: Optional[Path] = None
        self._setup_audit()
    
    def _setup_console_handler(self) -> None:
        """Configura handler para console."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.log_level))
        console_handler.setFormatter(self._get_formatter(console=True))
        self._logger.addHandler(console_handler)
    
    def _setup_file_handler(self) -> None:
        """Configura handler para arquivo."""
        # Cria diretório
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handler rotativo
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, self.log_level))
        file_handler.setFormatter(self._get_formatter(console=False))
        self._logger.addHandler(file_handler)
    
    def _setup_audit(self) -> None:
        """Configura log de auditoria."""
        audit_path = Path(self.log_file).parent / "audit.log"
        self._audit_log = audit_path
    
    def _get_formatter(self, console: bool = True) -> logging.Formatter:
        """Retorna o formatador apropriado."""
        if console:
            return logging.Formatter(
                "\033[36m%(asctime)s\033[0m | \033[32m%(levelname)-8s\033[0m | \033[33m%(name)s\033[0m | %(message)s",
                datefmt="%H:%M:%S"
            )
        else:
            return logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
    
    # ===== MÉTODOS DE LOG =====
    
    def debug(self, message: str, *args, **kwargs) -> None:
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self._logger.exception(message, *args, **kwargs)

    # ===== MÉTODOS ESPECIALIZADOS =====
    # ===== MÉTODOS ESPECIALIZADOS =====
    
    def system_event(self, event_type: str, data: Dict[str, Any] = None) -> None:
        """Registra um evento do sistema."""
        self.info(f"[SYSTEM] {event_type}: {json.dumps(data or {}, ensure_ascii=False)}")
    
    def user_action(self, user: str, action: str, data: Dict[str, Any] = None) -> None:
        """Registra uma ação do usuário."""
        self.info(f"[USER] {user} -> {action}: {json.dumps(data or {}, ensure_ascii=False)}")
    
    def module_event(self, module: str, event: str, data: Dict[str, Any] = None) -> None:
        """Registra um evento de módulo."""
        self.debug(f"[MODULE] {module} -> {event}: {json.dumps(data or {}, ensure_ascii=False)}")
    
    def audit(self, action: str, user: str, data: Dict[str, Any] = None) -> None:
        """
        Registra ação para auditoria.
        Isso nunca deve ser perdido.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user": user,
            "data": data or {}
        }
        
        # Log normal
        self.info(f"[AUDIT] {action} by {user}: {json.dumps(data or {}, ensure_ascii=False)}")
        
        # Log de auditoria (arquivo separado)
        if self._audit_log:
            try:
                with open(self._audit_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass
    
    def event_log(self, event: str, data: Dict[str, Any] = None) -> None:
        """Registra um evento para análise futura."""
        self.info(f"[EVENT] {event}: {json.dumps(data or {}, ensure_ascii=False)}")