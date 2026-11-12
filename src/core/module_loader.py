"""Carregador automático de módulos."""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import sys


class ModuleLoader:
    """
    Carrega módulos automaticamente.
    Procura módulos em diretórios e registra no ServiceRegistry.
    """
    
    def __init__(self, logger, service_registry):
        self.logger = logger
        self.registry = service_registry
        
        self._loaded_modules: Dict[str, Any] = {}
        self._module_paths: List[Path] = []
    
    def add_path(self, path: Path) -> None:
        """Adiciona um caminho para scanear."""
        if path.exists() and path.is_dir():
            self._module_paths.append(path)
            self.logger.debug(f"Caminho adicionado: {path}")
    
    def add_package(self, package_name: str) -> None:
        """Adiciona um pacote para scanear."""
        try:
            package = importlib.import_module(package_name)
            if hasattr(package, "__path__"):
                self._module_paths.append(Path(package.__path__[0]))
                self.logger.debug(f"Pacote adicionado: {package_name}")
        except ImportError:
            self.logger.warning(f"Pacote não encontrado: {package_name}")
    
    def scan(self) -> Dict[str, Any]:
        """
        Escaneia todos os caminhos e carrega módulos.
        Retorna módulos carregados.
        """
        self.logger.info("Scanando módulos...")
        
        for path in self._module_paths:
            self._scan_directory(path)
        
        self.logger.info(f"Scan concluído: {len(self._loaded_modules)} módulos encontrados")
        return self._loaded_modules
    
    def _scan_directory(self, path: Path) -> None:
        """Escaneia um diretório por módulos Python."""
        if not path.exists():
            return
        
        # Procura por arquivos .py
        for py_file in path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            module_name = py_file.stem
            self._load_module_from_file(path, module_name)
        
        # Procura por subdiretórios com __init__.py
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "__init__.py").exists():
                # É um pacote
                module_name = subdir.name
                self._load_module_from_package(path, module_name)
    
    def _load_module_from_file(self, path: Path, module_name: str) -> bool:
        """Carrega um módulo de um arquivo."""
        try:
            # Constrói o nome completo do módulo
            full_name = self._build_module_name(path, module_name)
            
            # Importa o módulo
            module = importlib.import_module(full_name)
            
            # Registra classes encontradas
            self._register_classes(module)
            
            self._loaded_modules[module_name] = module
            self.logger.debug(f"Módulo carregado: {module_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar {module_name}: {e}")
            return False
    
    def _load_module_from_package(self, path: Path, package_name: str) -> bool:
        """Carrega um pacote."""
        try:
            full_name = self._build_module_name(path, package_name)
            module = importlib.import_module(full_name)
            
            self._loaded_modules[package_name] = module
            self.logger.debug(f"Pacote carregado: {package_name}")
            
            # Escaneia submódulos
            if hasattr(module, "__path__"):
                for subpath in module.__path__:
                    self._scan_directory(Path(subpath))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar pacote {package_name}: {e}")
            return False
    
    def _build_module_name(self, path: Path, module_name: str) -> str:
        """Constrói o nome completo do módulo."""
        # Remove o caminho base
        rel_path = path.relative_to(Path.cwd())
        
        # Converte para nome de pacote
        parts = list(rel_path.parts)
        
        # Remove 'src' se presente
        if parts and parts[0] == "src":
            parts = parts[1:]
        
        # Adiciona o nome do módulo
        parts.append(module_name)
        
        return ".".join(parts)
    
    def _register_classes(self, module: Any) -> None:
        """Registra classes do módulo no ServiceRegistry."""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                # Pula classes internas
                if name.startswith("_"):
                    continue
                
                # Verifica se tem um método initialize ou start
                if hasattr(obj, "initialize") or hasattr(obj, "start"):
                    class_name = name.lower()
                    
                    # Tenta instanciar (se possível)
                    try:
                        # Verifica se o construtor não requer parâmetros obrigatórios
                        sig = inspect.signature(obj.__init__)
                        params = list(sig.parameters.keys())
                        
                        # Remove self e params com default
                        required = [p for p in params[1:] if sig.parameters[p].default == inspect.Parameter.empty]
                        
                        if len(required) == 0:
                            instance = obj()
                            self.registry.register(class_name, instance)
                            self.logger.debug(f"Classe registrada: {class_name}")
                    except Exception as e:
                        # Não conseguiu instanciar, apenas registra a classe
                        self.registry.register(class_name, obj)
                        self.logger.debug(f"Classe registrada (como tipo): {class_name}")
    
    def load(self, module_name: str) -> Optional[Any]:
        """Carrega um módulo específico."""
        try:
            module = importlib.import_module(module_name)
            self._loaded_modules[module_name] = module
            return module
        except ImportError as e:
            self.logger.error(f"Erro ao importar {module_name}: {e}")
            return None
    
    def reload(self, module_name: str) -> Optional[Any]:
        """Recarrega um módulo."""
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            return sys.modules[module_name]
        return self.load(module_name)
    
    def unload(self, module_name: str) -> bool:
        """Descarrega um módulo."""
        if module_name in sys.modules:
            del sys.modules[module_name]
            self._loaded_modules.pop(module_name, None)
            self.logger.info(f"Módulo descarregado: {module_name}")
            return True
        return False
    
    def list_modules(self) -> List[str]:
        """Lista módulos carregados."""
        return list(self._loaded_modules.keys())