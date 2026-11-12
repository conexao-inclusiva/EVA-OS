"""Agente de Controle de Computador."""

from typing import Dict, Any, Optional
from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class ComputerControlAgent(BaseAgent):
    """
    Agente especializado em controle de computador, gerenciamento de aplicativos
    e configuração do sistema.
    """

    __plugin_name__ = "computer_control_agent"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Agente para controle de computador e apps"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "computer", "system", "automation"]
    __plugin_capabilities__ = ["computer_control", "app_management", "system_config"]
    __plugin_requires__ = ["event_bus", "logger", "config"]

    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="computer_control")
        self._task_count = 0

    async def initialize(self) -> None:
        """Inicializa o agente."""
        await super().initialize()
        self.logger.info("ComputerControlAgent: Pronto para execução autônoma")

    async def start(self) -> None:
        """Inicia o agente."""
        if self._running:
            return
        await super().start()
        self.logger.info("ComputerControlAgent: Iniciado")

    async def shutdown(self) -> None:
        """Desliga o agente."""
        self.logger.info("ComputerControlAgent: Desligando...")
        await super().shutdown()

    async def health_check(self) -> Dict[str, Any]:
        """Verifica a saúde do agente."""
        health = await super().health_check()
        health.update({
            "tasks_processed": self._task_count
        })
        return health

    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa tarefas de controle via EventBus.
        
        Espera-se que o payload contenha 'action' e os parâmetros necessários
        para a 'computer_control_tool'.
        """
        self._task_count += 1
        action = task.get("action")
        
        self.logger.info(f"ComputerControlAgent: Processando ação '{action}'")

        # Roteia para a ferramenta via EventBus
        try:
            result = await self.event_bus.publish_async(
                "tool.execute",
                {
                    "tool": "computer_control",
                    "params": task,
                    "request_id": task.get("request_id")
                },
                source="computer_control_agent"
            )
            return {"success": True, "task": action}
        except Exception as e:
            self.logger.error(f"ComputerControlAgent falhou na tarefa {action}: {e}")
            return {"success": False, "error": str(e)}
