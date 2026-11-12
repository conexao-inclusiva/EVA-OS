"""Auto-otimizador do sistema."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import psutil


class SelfOptimizer:
    """
    Auto-otimizador da EVA.
    
    Responsabilidades:
    - Analisar performance do sistema
    - Identificar gargalos
    - Propor otimizações
    - Aplicar otimizações
    """
    
    def __init__(self, evolution_manager):
        self.evolution_manager = evolution_manager
        self.logger = evolution_manager.logger
        
        self._optimization_history: List[Dict[str, Any]] = []
        self._baseline_performance: Optional[Dict[str, Any]] = None
    
    async def optimize(self) -> Dict[str, Any]:
        """
        Executa otimização do sistema.
        """
        self.logger.info("Iniciando auto-otimização...")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "optimizations": [],
            "performance_gain": 0.0,
            "success": True
        }
        
        # 1. Analisa performance atual
        current_performance = self._analyze_performance()
        
        # 2. Identifica gargalos
        bottlenecks = self._identify_bottlenecks(current_performance)
        
        # 3. Gera otimizações
        for bottleneck in bottlenecks:
            optimization = await self._generate_optimization(bottleneck)
            if optimization:
                result["optimizations"].append(optimization)
                
                # Aplica otimização (simulado)
                await self._apply_optimization(optimization)
        
        # 4. Mede ganho
        if self._baseline_performance:
            gain = self._calculate_gain(self._baseline_performance, current_performance)
            result["performance_gain"] = gain
        
        # 5. Atualiza baseline
        self._baseline_performance = current_performance
        
        # 6. Registra histórico
        self._optimization_history.append(result)
        if len(self._optimization_history) > 50:
            self._optimization_history = self._optimization_history[-50:]
        
        self.logger.info(f"Otimização concluída: {len(result['optimizations'])} otimizações aplicadas")
        
        return result
    
    def _analyze_performance(self) -> Dict[str, Any]:
        """
        Analisa performance atual.
        """
        return {
            "cpu": psutil.cpu_percent(interval=0.5),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent,
            "timestamp": datetime.now().isoformat()
        }
    
    def _identify_bottlenecks(self, performance: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identifica gargalos.
        """
        bottlenecks = []
        
        # CPU alta
        if performance.get("cpu", 0) > 70:
            bottlenecks.append({
                "type": "cpu",
                "description": f"CPU está em {performance['cpu']}%",
                "severity": "high" if performance['cpu'] > 85 else "medium"
            })
        
        # Memória alta
        if performance.get("memory", 0) > 80:
            bottlenecks.append({
                "type": "memory",
                "description": f"Memória está em {performance['memory']}%",
                "severity": "high" if performance['memory'] > 90 else "medium"
            })
        
        # Disco alto
        if performance.get("disk", 0) > 85:
            bottlenecks.append({
                "type": "disk",
                "description": f"Disco está em {performance['disk']}%",
                "severity": "medium"
            })
        
        return bottlenecks
    
    async def _generate_optimization(self, bottleneck: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Gera otimização para um gargalo.
        """
        optimizations = {
            "cpu": [
                {
                    "type": "cpu_optimization",
                    "description": "Reduzir threads em background",
                    "action": "reduce_threads"
                },
                {
                    "type": "cpu_optimization",
                    "description": "Aumentar cache de resultados",
                    "action": "increase_cache"
                }
            ],
            "memory": [
                {
                    "type": "memory_optimization",
                    "description": "Limpar cache de memória",
                    "action": "clear_cache"
                },
                {
                    "type": "memory_optimization",
                    "description": "Compactar estrutura de dados",
                    "action": "compact_data"
                }
            ],
            "disk": [
                {
                    "type": "disk_optimization",
                    "description": "Limpar logs antigos",
                    "action": "clean_logs"
                },
                {
                    "type": "disk_optimization",
                    "description": "Comprimir arquivos de histórico",
                    "action": "compress_history"
                }
            ]
        }
        
        return optimizations.get(bottleneck.get("type"), [{}])[0]
    
    async def _apply_optimization(self, optimization: Dict[str, Any]) -> bool:
        """
        Aplica uma otimização.
        """
        self.logger.info(f"Aplicando otimização: {optimization.get('description')}")
        # TODO: Implementar aplicação real
        return True
    
    def _calculate_gain(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> float:
        """
        Calcula ganho de performance.
        """
        gain = 0.0
        
        # CPU ganho
        cpu_baseline = baseline.get("cpu", 0)
        cpu_current = current.get("cpu", 0)
        if cpu_baseline > 0:
            gain += (cpu_baseline - cpu_current) / cpu_baseline * 0.3
        
        # Memória ganho
        mem_baseline = baseline.get("memory", 0)
        mem_current = current.get("memory", 0)
        if mem_baseline > 0:
            gain += (mem_baseline - mem_current) / mem_baseline * 0.3
        
        # Disco ganho
        disk_baseline = baseline.get("disk", 0)
        disk_current = current.get("disk", 0)
        if disk_baseline > 0:
            gain += (disk_baseline - disk_current) / disk_baseline * 0.4
        
        return gain * 100