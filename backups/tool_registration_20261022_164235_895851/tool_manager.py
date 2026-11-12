"""Gerenciador de ferramentas da EVA."""

import asyncio
from typing import Dict, Any, Optional, List, Type
from datetime import datetime

from src.kernel.events import Event, EventBus
from src.tools.base_tool import BaseTool
from src.tools.tool_registry import ToolRegistry
from src.tools.tool_executor import ToolExecutor
from src.tools.tool_permission import ToolPermission
from src.tools.tool_context import ToolContext
from src.security.tool_execution_policy import ToolExecutionPolicy


class ToolManager:
    """
    Gerenciador de ferramentas da EVA.
    """
    
    __plugin_name__ = "tool_manager"
    __plugin_version__ = "1.0.0"
    __plugin_description__ = "Gerenciador de ferramentas da EVA"
    __plugin_author__ = "EVA OS Team"
    __plugin_tags__ = ["core", "tools", "execution"]
    __plugin_capabilities__ = ["tool_management"]
    __plugin_requires__ = ["event_bus", "logger", "config"]
    
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        
        self.registry = ToolRegistry()
        self.executor = ToolExecutor(self)
        self.permission = ToolPermission(self)
        self.execution_policy = ToolExecutionPolicy()
        self.context = ToolContext(self)
        
        self._tools: Dict[str, BaseTool] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300
        self._running = False
        
        self._register_listeners()
        self.logger.info("ToolManager inicializado")
    
    def _register_listeners(self) -> None:
        self.event_bus.subscribe("tool.register", self._on_register)
        self.event_bus.subscribe("tool.execute", self._on_execute)
        self.event_bus.subscribe("tool.list", self._on_list)
        self.event_bus.subscribe("tool.get_info", self._on_get_info)
        self.event_bus.subscribe("tool.clear_cache", self._on_clear_cache)
    
    async def initialize(self) -> None:
        self.logger.info("ToolManager inicializando...")
        self._register_builtin_tools()
        self._running = True
        self.logger.info(f"ToolManager inicializado com {len(self._tools)} ferramentas")
    
    async def start(self) -> None:
        self.logger.info("ToolManager iniciando...")
        self.logger.info("ToolManager pronto")
    
    async def shutdown(self) -> None:
        self.logger.info("ToolManager desligando...")
        self._running = False
        self._cache.clear()
        self.logger.info("ToolManager desligado")
    
    def _register_builtin_tools(self) -> None:
        try:
            from src.tools.builtin.python_tool import PythonTool
            from src.tools.builtin.shell_tool import ShellTool
            from src.tools.builtin.file_tool import FileTool
            from src.tools.builtin.network_tool import NetworkTool
            from src.tools.builtin.system_tool import SystemTool
            from src.tools.builtin.date_tool import DateTool
            
            self.register_tool(PythonTool)
            self.register_tool(ShellTool)
            self.register_tool(FileTool)
            self.register_tool(NetworkTool)
            self.register_tool(SystemTool)
            self.register_tool(DateTool)
            
        except Exception as e:
            self.logger.error(f"Erro ao registrar ferramentas built-in: {e}")
    
    def register_tool(self, tool_class: Type[BaseTool]) -> bool:
        try:
            tool = tool_class(logger=self.logger, config=self.config)
            self._tools[tool.name] = tool
            self.registry.register(tool.name, tool_class, {
                "name": tool.name,
                "capabilities": tool.get_capabilities(),
                "permissions": tool.get_permissions(),
                "required_params": tool.get_required_params(),
                "optional_params": tool.get_optional_params()
            })
            self.logger.info(f"Ferramenta registrada: {tool.name}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao registrar ferramenta: {e}")
            return False
    
    async def _on_register(self, event: Event) -> None:
        payload = event.payload
        tool_class_path = payload.get("tool_class")
        
        if not tool_class_path:
            await self._send_error("no_tool_class", "Nenhuma classe de ferramenta fornecida")
            return
        
        try:
            module_path, class_name = tool_class_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            tool_class = getattr(module, class_name)
            success = self.register_tool(tool_class)
            
            await self.event_bus.publish_async(
                "tool.registered",
                {
                    "success": success,
                    "tool_class": tool_class_path,
                    "timestamp": datetime.now().isoformat()
                },
                source="tool_manager"
            )
        except Exception as e:
            self.logger.error(f"Erro ao registrar ferramenta via evento: {e}")
    
    async def _on_execute(self, event: Event) -> None:
        payload = event.payload
        if not isinstance(payload, dict):
            await self._send_error("invalid_request", "Payload invalido")
            return

        tool_name = payload.get("tool")
        params = payload.get("params", {})
        context = payload.get("context", {})
        request_id = payload.get("request_id")
        if not isinstance(tool_name, str) or not tool_name:
            await self._send_error("no_tool", "Ferramenta invalida", request_id)
            return
        if not isinstance(params, dict) or not isinstance(context, dict):
            await self._send_error("invalid_request", "Parametros ou contexto invalidos", request_id)
            return
        if "user" in context and not isinstance(context["user"], dict):
            await self._send_error("invalid_context", "Usuario invalido", request_id)
            return
        role = context.get("user", {}).get("role", "guest")
        if not isinstance(role, str):
            await self._send_error("invalid_context", "Papel invalido", request_id)
            return

        # A permissao e verificada inclusive para resultados em cache.
        # Isto nao autentica o papel recebido no contexto.
        if (
            not self.execution_policy.authorize(
                tool_name, params, context
            ).allowed
            or not self.permission.check(tool_name, context)
        ):
            await self.event_bus.publish_async(
                "tool.execution_result",
                {
                    "result": {
                        "success": False,
                        "error": "Permissao negada para ferramenta: " + tool_name,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "cached": False,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat(),
                },
                source="tool_manager",
            )
            return

        # Diagnosticos de rede devem produzir uma observacao nova.
        use_cache = payload.get("use_cache", True) is True and tool_name != "network"
        user = context.get("user", {})
        outer_id = context.get("user_id")
        inner_id = user.get("user_id")
        user_id = outer_id if outer_id is not None else inner_id
        if (not isinstance(user_id, str) or not user_id.strip()
                or (outer_id is not None and inner_id is not None
                    and outer_id != inner_id)):
            use_cache = False

        cache_key = None
        if use_cache:
            try:
                import json
                cache_key = json.dumps(
                    [tool_name, params, context],
                    sort_keys=True, ensure_ascii=True, allow_nan=False,
                )
            except (TypeError, ValueError, OverflowError, RecursionError):
                use_cache = False

        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = (datetime.now() - datetime.fromisoformat(cached["timestamp"])).total_seconds()
            if 0 <= age < self._cache_ttl:
                await self.event_bus.publish_async(
                    "tool.execution_result",
                    {
                        "result": cached["result"],
                        "cached": True,
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                    source="tool_manager",
                )
                return

        result = await self.execute_tool(tool_name, params, context)
        if result.get("success") and use_cache:
            self._cache[cache_key] = {
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }

        await self.event_bus.publish_async(
            "tool.execution_result",
            {
                "result": result,
                "cached": False,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
            },
            source="tool_manager",
        )

    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any],
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        tool = self._tools.get(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Ferramenta não encontrada: {tool_name}",
                "timestamp": datetime.now().isoformat()
            }
        
        if (
            not self.execution_policy.authorize(
                tool_name, params, context
            ).allowed
            or not self.permission.check(tool_name, context or {})
        ):
            return {
                "success": False,
                "error": f"Permissão negada para ferramenta: {tool_name}",
                "timestamp": datetime.now().isoformat()
            }
        
        return await tool.execute_with_validation(params, context)
    
    async def _on_list(self, event: Event) -> None:
        request_id = event.payload.get("request_id")
        tools = self.list_tools()
        
        await self.event_bus.publish_async(
            "tool.list_result",
            {
                "tools": tools,
                "count": len(tools),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="tool_manager"
        )
    
    async def _on_get_info(self, event: Event) -> None:
        payload = event.payload
        tool_name = payload.get("tool")
        request_id = payload.get("request_id")
        info = self.get_tool_info(tool_name)
        
        await self.event_bus.publish_async(
            "tool.info",
            {
                "tool": tool_name,
                "info": info,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="tool_manager"
        )
    
    async def _on_clear_cache(self, event: Event) -> None:
        self._cache.clear()
        self.logger.info("Cache de ferramentas limpo")
        await self.event_bus.publish_async(
            "tool.cache_cleared",
            {"timestamp": datetime.now().isoformat()},
            source="tool_manager"
        )
    
    async def _send_error(self, code: str, message: str, request_id: Optional[str] = None) -> None:
        await self.event_bus.publish_async(
            "tool.error",
            {
                "code": code,
                "message": message,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            },
            source="tool_manager"
        )
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)
    
    def get_tool_info(self, name: str) -> Optional[Dict[str, Any]]:
        tool = self._tools.get(name)
        if tool:
            return {
                **tool.get_info(),
                "stats": tool.get_stats(),
                "permissions": tool.get_permissions()
            }
        return None
    
    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "capabilities": tool.get_capabilities(),
                "stats": tool.get_stats(),
                "info": tool.get_info()
            }
            for name, tool in self._tools.items()
        ]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
            "keys": list(self._cache.keys())[:10]
        }
    
    async def health_check(self) -> dict:
        return {
            "status": "running" if self._running else "stopped",
            "total_tools": len(self._tools),
            "cache_size": len(self._cache),
            "tools": {
                name: tool.get_stats()
                for name, tool in self._tools.items()
            }
        }