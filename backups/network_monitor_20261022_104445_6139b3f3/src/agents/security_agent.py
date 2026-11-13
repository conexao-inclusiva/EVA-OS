"""Agente de Segurança."""

from typing import Dict, Any, Optional
from datetime import datetime

from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class SecurityAgent(BaseAgent):
    """
    Agente de Segurança.
    
    Responsável por:
    - Monitorar ameaças
    - Responder a emergências
    - Gerenciar permissões
    - Auditoria
    """
    
    __plugin_name__ = "security_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente especializado em segurança"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "security", "emergency"]
    __plugin_capabilities__ = ["security", "emergency", "monitoring"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="security")
        self._alerts = []
        self._incidents = []
    
    async def initialize(self) -> None:
        """Inicializa o agente; nao inicia monitoramento de equipamentos."""
        await super().initialize()
        self.logger.info("SecurityAgent: inicializado; monitoramento nao configurado")

    async def start(self) -> None:
        """Inicia o ciclo de vida do agente, sem acionar equipamentos."""
        if not self._initialized:
            raise RuntimeError("SecurityAgent deve ser inicializado antes de start")
        if not self._running:
            await super().start()

    
    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de segurança.
        """
        task_type = task.get("type", "check")
        
        if task_type == "check":
            return await self._handle_check(task)
        elif task_type == "alert":
            return await self._handle_alert(task)
        elif task_type == "emergency":
            return await self._handle_emergency(task)
        elif task_type == "status":
            return await self._handle_status(task)
        else:
            return {"error": f"Tipo de tarefa desconhecido: {task_type}"}
    
    async def _handle_check(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Informa honestamente a ausencia de verificacoes integradas."""
        return {
            "type": "check",
            "success": False,
            "status": "not_configured",
            "message": "Nenhuma verificacao de seguranca foi executada.",
            "checks": [],
            "read_only": True,
            "timestamp": datetime.now().isoformat()
        }

    
    async def _handle_alert(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula alerta de segurança."""
        alert = task.get("alert", {})
        self._alerts.append({
            "alert": alert,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "type": "alert",
            "alert": alert,
            "acknowledged": True,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _handle_emergency(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Registra o relato e retorna orientacoes; nao executa protocolos."""
        incident = task.get("incident", {})
        if not isinstance(incident, dict):
            return {
                "type": "emergency",
                "success": False,
                "error": "incident deve ser um dicionario",
                "executed": False,
                "timestamp": datetime.now().isoformat()
            }

        self._incidents.append({
            "incident": dict(incident),
            "timestamp": datetime.now().isoformat()
        })
        incident_type = incident.get("type")
        if incident_type == "fire":
            protocol = "fire_protocol"
            steps = ["Buscar local seguro", "Solicitar ajuda humana de emergencia"]
        elif incident_type == "break_in":
            protocol = "security_protocol"
            steps = ["Buscar local seguro", "Solicitar ajuda humana de seguranca"]
        else:
            protocol = "emergency_protocol"
            steps = ["Solicitar avaliacao humana da situacao"]

        self.logger.warning(
            "SecurityAgent: relato registrado; nenhuma acao externa executada"
        )
        return {
            "type": "emergency",
            "success": True,
            "status": "guidance_only",
            "action": "none",
            "suggested_protocol": protocol,
            "steps": steps,
            "executed": False,
            "external_actions": [],
            "requires_human_review": True,
            "equipment_changes_require_approval": True,
            "message": "Relato registrado em memoria; orientacoes nao executadas.",
            "timestamp": datetime.now().isoformat()
        }

    
    async def _handle_status(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manipula consulta de status."""
        return {
            "type": "status",
            "alerts": len(self._alerts),
            "incidents": len(self._incidents),
            "last_alert": self._alerts[-1] if self._alerts else None,
            "timestamp": datetime.now().isoformat()
        }
    
    async def shutdown(self) -> None:
        """Desliga o agente."""
        self.logger.info(f"SecurityAgent: {len(self._alerts)} alertas, {len(self._incidents)} incidentes")
        await super().shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do agente."""
        health = await super().health_check()
        health["alerts"] = len(self._alerts)
        health["incidents"] = len(self._incidents)
        return health