"""Módulo de Evolução da EVA OS."""

from src.evolution.evolution_manager import EvolutionManager
from src.evolution.self_optimizer import SelfOptimizer
from src.evolution.code_generator import CodeGenerator
from src.evolution.module_updater import ModuleUpdater
from src.evolution.version_manager import VersionManager
from src.evolution.rollback_manager import RollbackManager
from src.evolution.compatibility_checker import CompatibilityChecker
from src.evolution.performance_analyzer import PerformanceAnalyzer
from src.evolution.safe_runner import SafeRunner

__all__ = [
    "EvolutionManager",
    "SelfOptimizer",
    "CodeGenerator",
    "ModuleUpdater",
    "VersionManager",
    "RollbackManager",
    "CompatibilityChecker",
    "PerformanceAnalyzer",
    "SafeRunner"
]