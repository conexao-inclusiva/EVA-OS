"""Agente de Controle de Computador."""

from typing import Dict, Any, Optional
from src.agents.base_agent import BaseAgent
from src.kernel.events import EventBus


class ComputerControlAgent(BaseAgent):
    """
    Agente especializado em controle de computador, gerenciamento de aplicativos,
    navegação web e execução de comandos do sistema.
    """

    __plugin_name__ = "computer_control_agent"
    __plugin_version__ = "1.1.0"
    __plugin_description__ = "Agente para controle de computador, apps e comandos do sistema"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["agent", "computer", "system", "automation", "control"]
    __plugin_capabilities__ = ["computer_control", "app_management", "system_config", "web_navigation"]
    __plugin_requires__ = ["event_bus", "logger", "config"]

    def __init__(self, event_bus: EventBus, logger, config):
        super().__init__(event_bus, logger, config, name="computer_control")
        self._task_count = 0
        self._last_task_status = "idle"
        self.memory_manager = None

    async def initialize(self) -> None:
        """Inicializa o agente e resolve dependências do núcleo."""
        self.logger.info("ComputerControlAgent: Inicializando componentes...")
        
        # Tenta obter o MemoryManager do registro de serviços se disponível
        try:
            registry = getattr(self, "service_registry", None)
            if registry:
                self.memory_manager = registry.get("memory_manager")
                if not self.memory_manager:
                    self.logger.warning("ComputerControlAgent: MemoryManager não encontrado no registro de serviços.")
            else:
                self.logger.warning("ComputerControlAgent: ServiceRegistry não disponível.")
        except Exception as e:
            self.logger.error(f"ComputerControlAgent: Erro ao resolver dependências: {e}")
        
        await super().initialize()
        self.logger.info("ComputerControlAgent: Inicialização concluída e capacidades registradas")

    async def start(self) -> None:
        """Inicia o agente verificando o estado do barramento."""
        if self._running:
            return
            
        if not self.event_bus:
            self.logger.error("ComputerControlAgent: Falha ao iniciar - EventBus ausente")
            return

        try:
            await super().start()
            self._last_task_status = "ready"
            self.logger.info("ComputerControlAgent: Ativo e pronto para processar solicitações")
        except Exception as e:
            self.logger.error(f"ComputerControlAgent: Erro crítico no início: {e}")
            self._last_task_status = "failed"
            raise

    async def shutdown(self) -> None:
        """Encerra o agente limpando o estado operacional."""
        self.logger.info("ComputerControlAgent: Iniciando encerramento...")
        self._last_task_status = "shutdown"
        await super().shutdown()
        self.logger.info("ComputerControlAgent: Encerrado corretamente")

    async def health_check(self) -> Dict[str, Any]:
        """Retorna o estado de saúde e métricas do agente."""
        health = await super().health_check()
        health.update({
            "tasks_processed": self._task_count,
            "status": self._last_task_status,
            "has_memory_manager": self.memory_manager is not None,
            "version": self.__plugin_version__
        })
        return health

    async def process(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa solicitações de controle enviando eventos para a ferramenta correspondente.
        
        Suporta ações como: open_app, open_url, execute_command, list_apps, close_app, etc.
        """
        if not self._running:
            self.logger.error("ComputerControlAgent: Tentativa de processar tarefa enquanto desligado")
            return {"success": False, "error": "Agente inativo"}

        self._task_count += 1
        action = task.get("action")
        
        if not action:
            self.logger.warning("ComputerControlAgent: Payload da tarefa inválido - 'action' ausente")
            return {"success": False, "error": "Campo 'action' obrigatório"}

        self.logger.info(f"ComputerControlAgent: Executando comando de sistema: {action}")
        self._last_task_status = f"executing_{action}"

        try:
            # Roteia a execução para a ComputerControlTool via barramento de eventos
            # A ferramenta está registrada no sistema de ferramentas
            await self.event_bus.publish_async(
                "tool.execute",
                {
                    "tool": "computer_control",
                    "params": task,
                    "request_id": task.get("request_id"),
                    "context": task.get("context", {})
                },
                source="computer_control_agent"
            )
            
            self._last_task_status = "idle"
            return {
                "success": True, 
                "action": action,
                "status": "dispatched",
                "message": f"Solicitação de {action} enviada para o executor de ferramentas"
            }
        except Exception as e:
            self.logger.error(f"ComputerControlAgent: Falha ao publicar evento para {action}: {e}")
            self._last_task_status = "error"
            return {"success": False, "error": str(e)}
