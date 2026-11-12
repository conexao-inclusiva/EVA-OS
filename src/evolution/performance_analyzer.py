"""Analisador de performance."""

from typing import Dict, Any, List
import psutil
import time


class PerformanceAnalyzer:
    """
    Analisa performance do sistema.
    
    Responsabilidades:
    - Medir performance
    - Identificar degradações
    - Gerar relatórios
    """
    
    def __init__(self, evolution_manager):
        self.evolution_manager = evolution_manager
        self.logger = evolution_manager.logger
        
        self._metrics_history: List[Dict[str, Any]] = []
    
    async def analyze(self) -> Dict[str, Any]:
        """
        Analisa performance atual.
        """
        metrics = {
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "cpu": psutil.cpu_percent(interval=0.5),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent,
            "network": self._get_network_stats(),
            "uptime": time.time() - psutil.boot_time()
        }
        
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-100:]
        
        return metrics
    
    def _get_network_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de rede.
        """
        try:
            net = psutil.net_io_counters()
            return {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv
            }
        except:
            return {}
    
    async def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtém histórico de métricas.
        """
        return self._metrics_history[-limit:]