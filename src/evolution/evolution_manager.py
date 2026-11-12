"""
Gerenciador de evolução da EVA.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from src.kernel.events import Event, EventBus
from src.evolution.self_optimizer import SelfOptimizer
from src.evolution.code_generator import CodeGenerator
from src.evolution.module_updater import ModuleUpdater
from src.evolution.version_manager import VersionManager
from src.evolution.rollback_manager import RollbackManager
from src.evolution.compatibility_checker import CompatibilityChecker
from src.evolution.performance_analyzer import PerformanceAnalyzer
from src.evolution.safe_runner import SafeRunner

# 🔥 IMPORTE DO CORAÇÃO DA EVA
from src.kernel.policy_engine import get_policy_engine


class EvolutionManager:
    """
    Gerenciador de evolução da EVA.
    
    Responsabilidades:
    - Auto-otimização do sistema
    - Geração automática de código
    - Atualização de módulos
    - Gerenciamento de versões
    - Rollback seguro
    - Análise de performance
    """
    
    __plugin_name__ = "evolution_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de evolução da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "evolution", "self_improvement"]
    __plugin_capabilities__ = ["evolution", "self_optimization", "code_generation"]
    __plugin_requires__ = ["event_bus", "logger", "config", "learning_manager"]
    
    def __init__(self, event_bus: EventBus, logger, config, learning_manager):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self.learning_manager = learning_manager
        
        # Componentes
        self.self_optimizer = SelfOptimizer(self)
        self.code_generator = CodeGenerator(self)
        self.module_updater = ModuleUpdater(self)
        self.version_manager = VersionManager(self)
        self.rollback_manager = RollbackManager(self)
        self.compatibility_checker = CompatibilityChecker(self)
        self.performance_analyzer = PerformanceAnalyzer(self)
        self.safe_runner = SafeRunner(self)
        
        # Estado
        self._running = False
        self._evolution_task: Optional[asyncio.Task] = None
        self._evolution_interval = 3600  # 1 hora
        
        # Histórico de evoluções
        self._evolution_history: List[Dict[str, Any]] = []
        self._current_version = "1.0.0"
        self._pending_changes: List[Dict[str, Any]] = []
        
        # 🔥 Instância do PolicyEngine
        self.policy = get_policy_engine()
        
        # Registra listeners
        self._register_listeners()
        
        self.logger.info("EvolutionManager inicializado")
    
    def _register_listeners(self) -> None:
        """Registra ouvintes de eventos."""
        # Comandos
        self.event_bus.subscribe("evolution.optimize", self._on_optimize)
        self.event_bus.subscribe("evolution.generate", self._on_generate)
        self.event_bus.subscribe("evolution.update", self._on_update)
        self.event_bus.subscribe("evolution.rollback", self._on_rollback)
        self.event_bus.subscribe("evolution.version", self._on_version)
        self.event_bus.subscribe("evolution.status", self._on_status)
        
        # Eventos automáticos
        self.event_bus.subscribe("learning.analysis_complete", self._on_analysis_complete)
        self.event_bus.subscribe("system.error", self._on_system_error)
        self.event_bus.subscribe("performance.degraded", self._on_performance_degraded)
    
    async def initialize(self) -> None:
        """Inicializa o EvolutionManager."""
        self.logger.info("EvolutionManager inicializando...")
        
        # Carrega histórico
        await self._load_history()
        
        self._running = True
        
        # Inicia evolução automática
        self._evolution_task = asyncio.create_task(self._auto_evolve())
        
        self.logger.info("EvolutionManager inicializado")
    
    async def start(self) -> None:
        """Inicia o EvolutionManager."""
        self.logger.info("EvolutionManager iniciando...")
        self.logger.info("EvolutionManager pronto")
    
    async def shutdown(self) -> None:
        """Desliga o EvolutionManager."""
        self.logger.info("EvolutionManager desligando...")
        
        self._running = False
        
        if self._evolution_task:
            self._evolution_task.cancel()
            try:
                await self._evolution_task
            except asyncio.CancelledError:
                pass
        
        await self._save_history()
        
        self.logger.info("EvolutionManager desligado")
    
    # ===== COMANDOS =====
    
    async def _on_optimize(self, event: Event) -> None:
        """Solicita otimização."""
        payload = event.payload
        request_id = payload.get("request_id")
        
        # 🔥 Verifica com o PolicyEngine
        if not self.policy.check_action("optimize_system", "self_optimizer"):
            self.logger.warning("⛔ Otimização bloqueada pelo PolicyEngine.")
            await self.event_bus.publish_async(
                "evolution.optimization_result",
                {
                    "result": {"success": False, "error": "Blocked by PolicyEngine"},
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="evolution_manager"
            )
            return
        
        result = await self.self_optimizer.optimize()
        
        await self.event_bus.publish_async(
            "evolution.optimization_result",
            {
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    async def _on_generate(self, event: Event) -> None:
        """Solicita geração de código."""
        payload = event.payload
        description = payload.get("description", "")
        module = payload.get("module", "")
        request_id = payload.get("request_id")
        
        # 🔥 Verifica com o PolicyEngine
        if not self.policy.check_action(f"generate_code: {description}", module):
            self.logger.warning(f"⛔ Geração de código bloqueada pelo PolicyEngine. Módulo: {module}")
            await self.event_bus.publish_async(
                "evolution.generation_result",
                {
                    "result": {"success": False, "error": "Blocked by PolicyEngine"},
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="evolution_manager"
            )
            return
        
        result = await self.code_generator.generate(description, module)
        
        await self.event_bus.publish_async(
            "evolution.generation_result",
            {
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    async def _on_update(self, event: Event) -> None:
        """Solicita atualização de módulo."""
        payload = event.payload
        module = payload.get("module", "")
        version = payload.get("version", "latest")
        request_id = payload.get("request_id")
        
        # 🔥 Verifica com o PolicyEngine
        if not self.policy.check_action(f"update_module: {module}", module):
            self.logger.warning(f"⛔ Atualização bloqueada pelo PolicyEngine. Módulo: {module}")
            await self.event_bus.publish_async(
                "evolution.update_result",
                {
                    "result": {"success": False, "error": "Blocked by PolicyEngine"},
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="evolution_manager"
            )
            return
        
        result = await self.module_updater.update(module, version)
        
        await self.event_bus.publish_async(
            "evolution.update_result",
            {
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    async def _on_rollback(self, event: Event) -> None:
        """Solicita rollback."""
        payload = event.payload
        module = payload.get("module", "")
        version = payload.get("version")
        request_id = payload.get("request_id")
        
        # 🔥 Verifica com o PolicyEngine
        if not self.policy.check_action(f"rollback_module: {module}", module):
            self.logger.warning(f"⛔ Rollback bloqueado pelo PolicyEngine. Módulo: {module}")
            await self.event_bus.publish_async(
                "evolution.rollback_result",
                {
                    "result": {"success": False, "error": "Blocked by PolicyEngine"},
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                },
                source="evolution_manager"
            )
            return
        
        result = await self.rollback_manager.rollback(module, version)
        
        await self.event_bus.publish_async(
            "evolution.rollback_result",
            {
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    async def _on_version(self, event: Event) -> None:
        """Solicita informações de versão."""
        payload = event.payload
        request_id = payload.get("request_id")
        
        versions = await self.version_manager.get_versions()
        
        await self.event_bus.publish_async(
            "evolution.version_info",
            {
                "current": self._current_version,
                "versions": versions,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    async def _on_status(self, event: Event) -> None:
        """Solicita status da evolução."""
        payload = event.payload
        request_id = payload.get("request_id")
        
        status = await self.get_status()
        
        await self.event_bus.publish_async(
            "evolution.status_result",
            {
                "status": status,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="evolution_manager"
        )
    
    # ===== EVENTOS AUTOMÁTICOS =====
    
    async def _on_analysis_complete(self, event: Event) -> None:
        """Análise de aprendizado concluída."""
        payload = event.payload
        result = payload.get("result", {})
        
        suggestions = result.get("suggestions", [])
        for suggestion in suggestions:
            if suggestion.get("priority") == "high":
                self._pending_changes.append({
                    "type": "suggestion",
                    "data": suggestion,
                    "timestamp": datetime.now().isoformat()
                })
        
        self.logger.info(f"{len(suggestions)} sugestões de melhoria recebidas")
    
    async def _on_system_error(self, event: Event) -> None:
        """Erro no sistema."""
        payload = event.payload
        error = payload.get("error", "Unknown error")
        module = payload.get("module", "unknown")
        
        if "critical" in str(error).lower():
            self.logger.warning(f"Erro crítico detectado. Tentando recuperação...")
            await self.rollback_manager.rollback(module)
    
    async def _on_performance_degraded(self, event: Event) -> None:
        """Performance degradada."""
        payload = event.payload
        metric = payload.get("metric", "unknown")
        value = payload.get("value", 0)
        threshold = payload.get("threshold", 0)
        
        self.logger.warning(f"Performance degradada: {metric} = {value} (threshold: {threshold})")
        asyncio.create_task(self.self_optimizer.optimize())
    
    # ===== EVOLUÇÃO AUTOMÁTICA =====
    
    async def _auto_evolve(self) -> None:
        """Loop de evolução automática."""
        while self._running:
            try:
                await asyncio.sleep(self._evolution_interval)
                
                if self._running:
                    if self._pending_changes:
                        self.logger.info(f"Processando {len(self._pending_changes)} mudanças pendentes...")
                        await self._process_pending_changes()
                    
                    if len(self._evolution_history) % 5 == 0:
                        await self.self_optimizer.optimize()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Erro na evolução automática: {e}")
    
    # 🔥 MÉTODO MODIFICADO PARA USAR O POLICY ENGINE
    async def _process_pending_changes(self) -> None:
        """Processa mudanças pendentes com validação do PolicyEngine."""
        changes = self._pending_changes.copy()
        self._pending_changes.clear()
        
        for change in changes:
            try:
                if change["type"] == "suggestion":
                    suggestion = change["data"]
                    module_name = suggestion.get("category", "general")
                    description = suggestion.get("description", "")
                    
                    # 🔥 VALIDA COM O POLICY ENGINE
                    is_valid, reason = self.policy.validate_code_change(
                        description,  # Passa a descrição como "código" para checagem de segurança
                        module_name
                    )
                    
                    if not is_valid:
                        self.logger.warning(f"⛔ Mudança bloqueada pelo PolicyEngine: {reason}")
                        self._evolution_history.append({
                            "type": "blocked_evolution",
                            "change": change,
                            "reason": reason,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # Gera código para a sugestão
                    code_result = await self.code_generator.generate(
                        description=description,
                        module=module_name
                    )
                    
                    if code_result.get("success"):
                        code = code_result.get("code", "")
                        
                        # 🔥 VALIDA O CÓDIGO GERADO
                        is_valid, reason = self.policy.validate_code_change(code, module_name)
                        
                        if not is_valid:
                            self.logger.warning(f"⛔ Código gerado bloqueado pelo PolicyEngine: {reason}")
                            self._evolution_history.append({
                                "type": "blocked_code",
                                "change": change,
                                "reason": reason,
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                        
                        # Aplica mudança
                        await self.module_updater.apply_code(
                            code,
                            module_name
                        )
                        
                        self.logger.info(f"Mudança aplicada: {suggestion.get('title')}")
                        
                        self._evolution_history.append({
                            "type": "auto_evolution",
                            "change": change,
                            "result": "success",
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                self.logger.error(f"Erro ao processar mudança: {e}")
    
    # ===== MÉTODOS PÚBLICOS =====
    
    async def get_status(self) -> Dict[str, Any]:
        """Obtém status da evolução."""
        return {
            "current_version": self._current_version,
            "evolution_count": len(self._evolution_history),
            "pending_changes": len(self._pending_changes),
            "is_running": self._running,
            "last_evolution": self._evolution_history[-1] if self._evolution_history else None,
            "timestamp": datetime.now().isoformat()
        }
    
    async def health_check(self) -> dict:
        """Health check do EvolutionManager."""
        return {
            "status": "running" if self._running else "stopped",
            "current_version": self._current_version,
            "evolution_count": len(self._evolution_history),
            "pending_changes": len(self._pending_changes)
        }
    
    # ===== PERSISTÊNCIA =====
    
    async def _load_history(self) -> None:
        """Carrega histórico."""
        # TODO: Implementar persistência
        pass
    
    async def _save_history(self) -> None:
        """Salva histórico."""
        # TODO: Implementar persistência
        pass