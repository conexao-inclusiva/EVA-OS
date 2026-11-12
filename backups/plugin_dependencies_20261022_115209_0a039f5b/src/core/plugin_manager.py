"""Plugin Manager - Sistema de carregamento dinâmico de módulos para EVA OS."""

import asyncio
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from uuid import uuid4
import hashlib
import json


class PluginStatus(Enum):
    """Status de um plugin."""
    DISCOVERED = auto()
    LOADING = auto()
    LOADED = auto()
    INITIALIZED = auto()
    STARTED = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    DEPRECATED = auto()
    INCOMPATIBLE = auto()


class PluginType(Enum):
    """Tipo de plugin."""
    CORE = auto()           # Componentes do Core
    MODULE = auto()         # Módulo funcional
    AGENT = auto()          # Agente
    TOOL = auto()           # Ferramenta
    INTERFACE = auto()      # Interface
    EXTENSION = auto()      # Extensão de terceiros
    LEGACY = auto()         # Compatibilidade


@dataclass
class PluginManifest:
    """Manifesto de um plugin."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = "EVA OS"
    
    plugin_type: PluginType = PluginType.MODULE
    
    # Dependências
    requires: List[str] = field(default_factory=list)  # Nomes de plugins
    requires_version: Dict[str, str] = field(default_factory=dict)  # Nome -> versão mínima
    
    # Compatibilidade
    eva_version_min: str = "1.0.0"
    eva_version_max: str = "99.0.0"
    
    # Entry points
    main_class: Optional[str] = None  # Nome da classe principal
    initialize_func: Optional[str] = None
    start_func: Optional[str] = None
    stop_func: Optional[str] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    
    # Assinatura/Verificação
    checksum: Optional[str] = None
    signature: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "plugin_type": self.plugin_type.name,
            "requires": self.requires,
            "requires_version": self.requires_version,
            "eva_version_min": self.eva_version_min,
            "eva_version_max": self.eva_version_max,
            "main_class": self.main_class,
            "tags": self.tags,
            "capabilities": self.capabilities,
            "checksum": self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        """Cria a partir de dicionário."""
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "EVA OS"),
            plugin_type=PluginType[data.get("plugin_type", "MODULE")],
            requires=data.get("requires", []),
            requires_version=data.get("requires_version", {}),
            eva_version_min=data.get("eva_version_min", "1.0.0"),
            eva_version_max=data.get("eva_version_max", "99.0.0"),
            main_class=data.get("main_class"),
            tags=data.get("tags", []),
            capabilities=data.get("capabilities", []),
            checksum=data.get("checksum")
        )


@dataclass
class Plugin:
    """Plugin carregado."""
    manifest: PluginManifest
    path: Path
    module: Optional[Any] = None
    instance: Optional[Any] = None
    status: PluginStatus = PluginStatus.DISCOVERED
    error: Optional[str] = None
    
    # Dependências resolvidas
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    # Timestamps
    discovered_at: datetime = field(default_factory=datetime.now)
    loaded_at: Optional[datetime] = None
    initialized_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    
    # Métricas
    load_time: float = 0.0
    import_time: float = 0.0
    init_time: float = 0.0
    
    def is_core(self) -> bool:
        """Verifica se é um plugin core."""
        return self.manifest.plugin_type == PluginType.CORE
    
    def is_compatible(self, eva_version: str) -> bool:
        """Verifica compatibilidade com versão da EVA."""
        # Versão simplificada - idealmente usar semver
        return True  # TODO: Implementar verificação semver


class PluginManager:
    """
    Gerenciador de Plugins da EVA.
    
    Características:
    - Descoberta automática de módulos
    - Resolução de dependências
    - Carregamento dinâmico
    - Hot reload
    - Sandbox (futuro)
    - Verificação de assinatura (futuro)
    - Compatibilidade entre versões
    """
    
    def __init__(self, logger, event_bus, config, service_registry):
        self.logger = logger
        self.event_bus = event_bus
        self.config = config
        self.registry = service_registry
        
        # Plugins
        self._plugins: Dict[str, Plugin] = {}
        self._plugins_by_name: Dict[str, str] = {}  # nome -> id
        
        # Caminhos de scan
        self._scan_paths: List[Path] = []
        
        # Padrões de exclusão
        self._exclude_patterns = {
            "__pycache__",
            "tests",
            "test",
            "venv",
            ".venv",
            "env",
            ".git",
            ".idea",
            ".vscode",
            "node_modules",
            "dist",
            "build"
        }
        
        # Plugins ignorados
        self._ignored_plugins: Set[str] = set()
        
        # Plugins carregados na ordem
        self._load_order: List[str] = []
        
        # Configuração
        self._auto_load = config.get("features.auto_load_plugins", True)
        self._enable_hot_reload = config.get("features.hot_reload", False)
        
        # Estado
        self._is_scanning = False
        self._is_loading = False
        
        self.logger.info("PluginManager inicializado")
    
    def add_scan_path(self, path: Path) -> None:
        """Adiciona um caminho para scanear."""
        if path.exists() and path.is_dir():
            self._scan_paths.append(path.resolve())
            self.logger.debug(f"Caminho adicionado: {path}")
        else:
            self.logger.warning(f"Caminho inválido: {path}")
    
    def add_exclude_pattern(self, pattern: str) -> None:
        """Adiciona um padrão de exclusão."""
        self._exclude_patterns.add(pattern)
    
    def ignore_plugin(self, name: str) -> None:
        """Ignora um plugin específico."""
        self._ignored_plugins.add(name)
        self.logger.debug(f"Plugin ignorado: {name}")
    
    async def scan(self) -> Dict[str, Plugin]:
        """
        Escaneia todos os caminhos em busca de plugins.
        Retorna dicionário de plugins encontrados.
        """
        if self._is_scanning:
            self.logger.warning("Scan já em andamento")
            return self._plugins
        
        self._is_scanning = True
        self.logger.info("Iniciando scan de plugins...")
        
        found = {}
        
        for path in self._scan_paths:
            plugins = await self._scan_directory(path)
            found.update(plugins)
        
        self._is_scanning = False
        self.logger.info(f"Scan concluído: {len(found)} plugins encontrados")
        
        # Atualiza plugins
        for plugin_id, plugin in found.items():
            if plugin_id not in self._plugins:
                self._plugins[plugin_id] = plugin
                self._plugins_by_name[plugin.manifest.name] = plugin_id
            else:
                # Atualiza existente
                existing = self._plugins[plugin_id]
                existing.status = plugin.status
                existing.path = plugin.path
        
        return self._plugins
    
    async def _scan_directory(self, path: Path, parent: Optional[Path] = None) -> Dict[str, Plugin]:
        """Escaneia um diretório recursivamente."""
        plugins = {}
        
        try:
            for item in path.iterdir():
                # Verifica exclusões
                if item.name in self._exclude_patterns:
                    continue
                
                if item.name.startswith("."):
                    continue
                
                if item.is_dir():
                    # Verifica se é um pacote Python (tem __init__.py)
                    init_file = item / "__init__.py"
                    if init_file.exists():
                        # É um pacote - procura por plugins dentro
                        sub_plugins = await self._scan_directory(item, path)
                        plugins.update(sub_plugins)
                    else:
                        # Diretório normal - pode ter arquivos .py
                        for py_file in item.glob("*.py"):
                            if py_file.name.startswith("__"):
                                continue
                            plugin = await self._discover_plugin(py_file, item)
                            if plugin:
                                plugins[plugin.manifest.id] = plugin
                
                elif item.is_file() and item.suffix == ".py":
                    if item.name.startswith("__"):
                        continue
                    plugin = await self._discover_plugin(item, parent or path)
                    if plugin:
                        plugins[plugin.manifest.id] = plugin
        
        except Exception as e:
            self.logger.error(f"Erro ao scanear {path}: {e}")
        
        return plugins
    
    async def _discover_plugin(self, file_path: Path, base_path: Path) -> Optional[Plugin]:
        """Descobre metadados sem instanciar o plugin."""
        try:
            file_path = file_path.resolve()
            module_name = self._get_module_name_from_path(file_path)
            if (module_name in self._ignored_plugins
                    or file_path.stem in self._ignored_plugins):
                return None
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                self.logger.debug(
                    "Falha ao importar " + module_name + ": " + type(exc).__name__
                )
                return None

            imported_path = getattr(module, "__file__", None)
            if imported_path is None or Path(imported_path).resolve() != file_path:
                self.logger.warning("Origem de modulo divergente: " + module_name)
                return None

            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                return None
            manifest = self._create_manifest_from_class(
                plugin_class, module_name, file_path
            )
            if manifest is None or manifest.name in self._ignored_plugins:
                return None
            return Plugin(
                manifest=manifest,
                path=file_path,
                module=module,
                status=PluginStatus.DISCOVERED,
            )
        except Exception as exc:
            self.logger.debug(
                "Falha na descoberta de " + str(file_path) + ": " + type(exc).__name__
            )
            return None

    
    def _find_plugin_class(self, module: Any) -> Optional[Type]:
        """Seleciona uma classe concreta definida pelo proprio modulo."""
        candidates = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_"):
                continue
            if obj.__module__ != module.__name__ or inspect.isabstract(obj):
                continue
            if not (hasattr(obj, "initialize") or hasattr(obj, "start")):
                continue
            if (hasattr(obj, "__plugin_name__")
                    or hasattr(obj, "__plugin_version__")):
                candidates.append(obj)
                continue
            try:
                parameters = list(inspect.signature(obj.__init__).parameters.values())[1:]
                required = [
                    parameter for parameter in parameters
                    if parameter.default is inspect.Parameter.empty
                    and parameter.kind not in (
                        inspect.Parameter.VAR_POSITIONAL,
                        inspect.Parameter.VAR_KEYWORD,
                    )
                ]
                if len(required) <= 2:
                    candidates.append(obj)
            except (TypeError, ValueError):
                continue

        module_leaf = module.__name__.rsplit(".", 1)[-1]
        matching = [
            cls for cls in candidates
            if cls.__dict__.get("__plugin_name__") == module_leaf
        ]
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            self.logger.warning("Classes de plugin ambiguas: " + module.__name__)
            return None

        declared = [
            cls for cls in candidates
            if "__plugin_name__" in cls.__dict__
            or "__plugin_version__" in cls.__dict__
        ]
        remaining = declared or candidates
        if len(remaining) == 1:
            return remaining[0]
        if len(remaining) > 1:
            self.logger.warning("Classes de plugin ambiguas: " + module.__name__)
        return None

    
    def _create_manifest_from_class(self, cls: Type, module_name: str, file_path: Path) -> Optional[PluginManifest]:
        """Cria um manifesto a partir de uma classe."""
        try:
            manifest = PluginManifest(
                name=getattr(cls, "__plugin_name__", module_name),
                version=getattr(cls, "__plugin_version__", "1.0.0"),
                description=getattr(cls, "__plugin_description__", ""),
                author=getattr(cls, "__plugin_author__", "EVA OS"),
                main_class=cls.__name__,
                plugin_type=self._detect_plugin_type(cls, module_name)
            )
            
            # Detecta dependências
            if hasattr(cls, "__plugin_requires__"):
                manifest.requires = cls.__plugin_requires__
            
            # Detecta tags
            if hasattr(cls, "__plugin_tags__"):
                manifest.tags = cls.__plugin_tags__
            
            # Detecta capabilities
            if hasattr(cls, "__plugin_capabilities__"):
                manifest.capabilities = cls.__plugin_capabilities__
            
            return manifest
            
        except Exception as e:
            self.logger.error(f"Erro ao criar manifesto para {cls.__name__}: {e}")
            return None
    
    def _detect_plugin_type(self, cls: Type, module_name: str) -> PluginType:
        """Detecta o tipo do plugin baseado no nome e classe."""
        type_map = {
            "agent": PluginType.AGENT,
            "tool": PluginType.TOOL,
            "interface": PluginType.INTERFACE,
            "core": PluginType.CORE,
            "memory": PluginType.MODULE,
            "knowledge": PluginType.MODULE,
            "planner": PluginType.MODULE,
            "consciousness": PluginType.MODULE
        }
        
        # Verifica por nome
        module_lower = module_name.lower()
        for key, plugin_type in type_map.items():
            if key in module_lower:
                return plugin_type
        
        # Verifica por métodos
        if hasattr(cls, "execute") or hasattr(cls, "run"):
            return PluginType.TOOL
        
        if hasattr(cls, "process") or hasattr(cls, "decide"):
            return PluginType.AGENT
        
        return PluginType.MODULE
    
    async def load_all(self) -> Dict[str, bool]:
        """
        Carrega todos os plugins descobertos.
        Resolve dependências e carrega na ordem correta.
        """
        if self._is_loading:
            self.logger.warning("Carregamento já em andamento")
            return {}
        
        self._is_loading = True
        self.logger.info("Carregando plugins...")
        
        results = {}
        
        # 1. Resolve dependências
        self._resolve_dependencies()
        
        # 2. Ordena topologicamente
        self._load_order = self._topological_sort()
        
        # 3. Carrega na ordem
        for plugin_id in self._load_order:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                success = await self._load_plugin(plugin)
                results[plugin.manifest.name] = success
                
                # Publica evento
                await self.event_bus.publish_async(
                    "PLUGIN_LOADED" if success else "PLUGIN_LOAD_FAILED",
                    {
                        "plugin": plugin.manifest.name,
                        "version": plugin.manifest.version,
                        "success": success,
                        "error": plugin.error if plugin.error else None
                    },
                    source="plugin_manager"
                )
        
        self._is_loading = False
        self.logger.info(f"Carregamento concluído: {sum(results.values())}/{len(results)} plugins")
        
        return results
    
    async def _load_plugin(self, plugin: Plugin) -> bool:
        """Carrega um plugin específico."""
        if plugin.status in [PluginStatus.LOADED, PluginStatus.INITIALIZED, PluginStatus.STARTED]:
            return True
        
        if plugin.manifest.name in self._ignored_plugins:
            plugin.status = PluginStatus.STOPPED
            plugin.error = "Plugin ignorado"
            return False
        
        try:
            plugin.status = PluginStatus.LOADING
            
            # Verifica dependências
            for dep_name in plugin.manifest.requires:
                if dep_name not in self._plugins_by_name:
                    plugin.status = PluginStatus.ERROR
                    plugin.error = f"Dependência não encontrada: {dep_name}"
                    self.logger.error(f"Plugin {plugin.manifest.name}: {plugin.error}")
                    return False
                
                dep_id = self._plugins_by_name[dep_name]
                dep = self._plugins.get(dep_id)
                if dep and dep.status not in [PluginStatus.LOADED, PluginStatus.INITIALIZED, PluginStatus.STARTED]:
                    plugin.status = PluginStatus.ERROR
                    plugin.error = f"Dependência não carregada: {dep_name}"
                    self.logger.error(f"Plugin {plugin.manifest.name}: {plugin.error}")
                    return False
            
            # Importa o módulo se ainda não foi
            if not plugin.module:
                # Reconstrói nome do módulo
                module_name = self._get_module_name_from_path(plugin.path)
                plugin.module = importlib.import_module(module_name)
            
            # Encontra a classe principal
            if plugin.manifest.main_class and plugin.module:
                cls = getattr(plugin.module, plugin.manifest.main_class, None)
                if cls:
                    # Instancia a classe
                    instance = await self._instantiate_plugin(cls, plugin)
                    if instance:
                        plugin.instance = instance
                        plugin.status = PluginStatus.LOADED
                        plugin.loaded_at = datetime.now()
                        
                        self.logger.info(f"Plugin carregado: {plugin.manifest.name} v{plugin.manifest.version}")
                        
                        # Registra no ServiceRegistry
                        self.registry.register(
                            plugin.manifest.name,
                            instance,
                            plugin.manifest.requires
                        )
                        
                        # Inicializa
                        if hasattr(instance, "initialize"):
                            try:
                                if asyncio.iscoroutinefunction(instance.initialize):
                                    await instance.initialize()
                                else:
                                    instance.initialize()
                                plugin.status = PluginStatus.INITIALIZED
                                plugin.initialized_at = datetime.now()
                            except Exception as e:
                                self.logger.error(f"Erro ao inicializar {plugin.manifest.name}: {e}")
                                plugin.error = str(e)
                                plugin.status = PluginStatus.ERROR
                                return False
                        
                        # Inicia
                        if hasattr(instance, "start"):
                            try:
                                if asyncio.iscoroutinefunction(instance.start):
                                    await instance.start()
                                else:
                                    instance.start()
                                plugin.status = PluginStatus.STARTED
                                plugin.started_at = datetime.now()
                            except Exception as e:
                                self.logger.error(f"Erro ao iniciar {plugin.manifest.name}: {e}")
                                plugin.error = str(e)
                                plugin.status = PluginStatus.ERROR
                                return False
                        
                        return True
            
            plugin.status = PluginStatus.ERROR
            plugin.error = "Classe principal não encontrada"
            return False
            
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.error = str(e)
            self.logger.error(f"Erro ao carregar plugin {plugin.manifest.name}: {e}")
            return False
    
    async def _instantiate_plugin(self, cls: Type, plugin: Plugin) -> Optional[Any]:
        """Instancia um plugin com injeção de dependências."""
        try:
            sig = inspect.signature(cls.__init__)
            params = list(sig.parameters.keys())
            
            kwargs = {}
            for param in params[1:]:  # Pula self
                param_type = sig.parameters[param].annotation
                if param_type != inspect.Parameter.empty:
                    # Tenta resolver pelo tipo
                    type_name = param_type.__name__.lower()
                    if self.registry.exists(type_name):
                        kwargs[param] = self.registry.get(type_name)
                    elif self.registry.exists(param):
                        kwargs[param] = self.registry.get(param)
                elif param == "event_bus":
                    kwargs[param] = self.registry.get("event_bus")
                elif param == "logger":
                    kwargs[param] = self.registry.get("logger")
                elif param == "config":
                    kwargs[param] = self.registry.get("config")
                elif param == "service_registry":
                    kwargs[param] = self.registry.get("service_registry")
            
            return cls(**kwargs)
            
        except Exception as e:
            self.logger.error(f"Erro ao instanciar {cls.__name__}: {e}")
            return None
    
    def _get_module_name_from_path(self, path: Path) -> str:
        """Preserva o pacote raiz no nome de importacao."""
        path = path.resolve()
        for root in path.parents:
            if root.name in ("src", "eva_os"):
                relative = path.relative_to(root.parent).with_suffix("")
                parts = list(relative.parts)
                if parts[-1] == "__init__":
                    parts.pop()
                if not parts or not all(part.isidentifier() for part in parts):
                    raise ValueError("Caminho de modulo invalido")
                return ".".join(parts)

        # Compatibilidade com outros pacotes Python explicitamente escaneados.
        parts = [] if path.stem == "__init__" else [path.stem]
        parent = path.parent
        while (parent / "__init__.py").is_file():
            parts.insert(0, parent.name)
            parent = parent.parent
        if not parts or not all(part.isidentifier() for part in parts):
            raise ValueError("Caminho de modulo invalido")
        return ".".join(parts)

    
    def _resolve_dependencies(self) -> None:
        """Resolve dependências entre plugins."""
        for plugin in self._plugins.values():
            plugin.dependencies = []
            for dep_name in plugin.manifest.requires:
                if dep_name in self._plugins_by_name:
                    dep_id = self._plugins_by_name[dep_name]
                    plugin.dependencies.append(dep_id)
        
        # Atualiza dependents
        for plugin in self._plugins.values():
            plugin.dependents = []
            for other in self._plugins.values():
                if plugin.manifest.id in other.dependencies:
                    plugin.dependents.append(other.manifest.id)
    
    def _topological_sort(self) -> List[str]:
        """
        Ordena plugins topologicamente por dependências.
        Plugins com menos dependências são carregados primeiro.
        """
        # Kahn's algorithm
        graph = {}
        in_degree = {}
        
        for plugin_id, plugin in self._plugins.items():
            graph[plugin_id] = plugin.dependencies.copy()
            in_degree[plugin_id] = len(plugin.dependencies)
        
        # Fila com plugins que não têm dependências
        queue = [pid for pid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            # Ordena por tipo (Core primeiro)
            queue.sort(key=lambda pid: 0 if self._plugins[pid].is_core() else 1)
            plugin_id = queue.pop(0)
            result.append(plugin_id)
            
            # Remove dependências de outros
            for other_id, deps in graph.items():
                if plugin_id in deps:
                    deps.remove(plugin_id)
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
        
        # Verifica ciclos
        if len(result) != len(self._plugins):
            self.logger.warning("Ciclo de dependência detectado!")
            # Tenta carregar mesmo assim (ordem atual)
            return list(self._plugins.keys())
        
        return result
    
    async def reload(self, plugin_name: str) -> bool:
        """Recarrega um plugin específico (hot reload)."""
        if not self._enable_hot_reload:
            self.logger.warning("Hot reload desabilitado")
            return False
        
        if plugin_name not in self._plugins_by_name:
            self.logger.warning(f"Plugin não encontrado: {plugin_name}")
            return False
        
        plugin_id = self._plugins_by_name[plugin_name]
        plugin = self._plugins[plugin_id]
        
        # Para o plugin
        if plugin.instance and hasattr(plugin.instance, "shutdown"):
            try:
                if asyncio.iscoroutinefunction(plugin.instance.shutdown):
                    await plugin.instance.shutdown()
                else:
                    plugin.instance.shutdown()
            except Exception as e:
                self.logger.error(f"Erro ao parar {plugin_name}: {e}")
        
        # Recarrega o módulo
        if plugin.module:
            try:
                importlib.reload(plugin.module)
            except Exception as e:
                self.logger.error(f"Erro ao recarregar módulo {plugin_name}: {e}")
                return False
        
        # Recarrega o plugin
        plugin.status = PluginStatus.DISCOVERED
        plugin.loaded_at = None
        plugin.initialized_at = None
        plugin.started_at = None
        plugin.instance = None
        
        return await self._load_plugin(plugin)
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Obtém um plugin pelo nome."""
        plugin_id = self._plugins_by_name.get(name)
        return self._plugins.get(plugin_id) if plugin_id else None
    
    def get_plugins(self, status: Optional[PluginStatus] = None) -> List[Plugin]:
        """Lista plugins, opcionalmente filtrando por status."""
        if status:
            return [p for p in self._plugins.values() if p.status == status]
        return list(self._plugins.values())
    
    def get_status_report(self) -> Dict[str, Any]:
        """Gera relatório de status dos plugins."""
        return {
            "total": len(self._plugins),
            "by_status": {
                status.name: len([p for p in self._plugins.values() if p.status == status])
                for status in PluginStatus
            },
            "plugins": {
                name: {
                    "version": p.manifest.version,
                    "status": p.status.name,
                    "type": p.manifest.plugin_type.name,
                    "error": p.error,
                    "dependencies": p.manifest.requires,
                    "load_time": p.load_time
                }
                for name, p in self._plugins.items()
            },
            "load_order": self._load_order,
            "scan_paths": [str(p) for p in self._scan_paths]
        }
    
    async def shutdown(self) -> None:
        """Desliga todos os plugins (ordem reversa)."""
        self.logger.info("Desligando plugins...")
        
        # Para na ordem reversa
        for plugin_id in reversed(self._load_order):
            plugin = self._plugins.get(plugin_id)
            if plugin and plugin.instance and hasattr(plugin.instance, "shutdown"):
                try:
                    if asyncio.iscoroutinefunction(plugin.instance.shutdown):
                        await plugin.instance.shutdown()
                    else:
                        plugin.instance.shutdown()
                    plugin.status = PluginStatus.STOPPED
                    self.logger.debug(f"Plugin parado: {plugin.manifest.name}")
                except Exception as e:
                    self.logger.error(f"Erro ao parar {plugin.manifest.name}: {e}")
        
        self.logger.info("Plugins desligados")