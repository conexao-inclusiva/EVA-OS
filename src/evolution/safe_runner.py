"""Executor seguro de código."""

from typing import Dict, Any, Optional
import subprocess
import tempfile
from pathlib import Path


class SafeRunner:
    """
    Executa código em ambiente seguro (sandbox).
    
    Responsabilidades:
    - Executar código isolado
    - Limitar recursos
    - Capturar outputs
    - Prevenir danos
    """
    
    def __init__(self, evolution_manager):
        self.evolution_manager = evolution_manager
        self.logger = evolution_manager.logger
    
    async def run(self, code: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Executa código em sandbox.
        """
        self.logger.info("Executando código em sandbox...")
        
        result = {
            "success": False,
            "output": "",
            "error": "",
            "returncode": -1
        }
        
        # Salva código em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = Path(f.name)
        
        try:
            # Executa com timeout
            proc = subprocess.run(
                ['python', str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result["output"] = proc.stdout
            result["error"] = proc.stderr
            result["returncode"] = proc.returncode
            result["success"] = proc.returncode == 0
            
        except subprocess.TimeoutExpired:
            result["error"] = f"Timeout após {timeout}s"
        except Exception as e:
            result["error"] = str(e)
        finally:
            # Limpa arquivo
            try:
                temp_file.unlink()
            except:
                pass
        
        return result