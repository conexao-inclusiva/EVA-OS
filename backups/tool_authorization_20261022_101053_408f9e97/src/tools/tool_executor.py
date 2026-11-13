"""Executor de ferramentas."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime


class ToolExecutor:
    """
    Executa ferramentas com gerenciamento de recursos.
    
    Responsabilidades:
    - Execução assíncrona
    - Timeout
    - Retry automático
    - Log de execução
    """
    
    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.logger = tool_manager.logger
        
        # Configurações
        self._default_timeout = 30  # segundos
        self._max_retries = 3
        self._retry_delay = 2  # segundos
        
        # Execuções em andamento
        self._executions: Dict[str, Dict[str, Any]] = {}
    
    async def execute(self, tool_name: str, params: Dict[str, Any],
                     context: Dict[str, Any] = None,
                     timeout: Optional[float] = None,
                     retries: Optional[int] = None) -> Dict[str, Any]:
        """
        Executa uma ferramenta com timeout e retry.
        """
        execution_id = f"{tool_name}_{datetime.now().timestamp()}"
        
        self._executions[execution_id] = {
            "tool": tool_name,
            "params": params,
            "started_at": datetime.now(),
            "status": "running"
        }
        
        try:
            result = await self._execute_with_retry(
                tool_name, params, context,
                timeout or self._default_timeout,
                retries or self._max_retries
            )
            
            self._executions[execution_id]["status"] = "completed"
            self._executions[execution_id]["completed_at"] = datetime.now()
            
            return result
            
        except asyncio.TimeoutError:
            self._executions[execution_id]["status"] = "timeout"
            return {
                "success": False,
                "error": f"Timeout após {timeout or self._default_timeout}s",
                "execution_id": execution_id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self._executions[execution_id]["status"] = "error"
            self._executions[execution_id]["error"] = str(e)
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            # Limpa execuções antigas
            self._cleanup_executions()
    
    async def _execute_with_retry(self, tool_name: str, params: Dict[str, Any],
                                  context: Dict[str, Any], timeout: float,
                                  max_retries: int) -> Dict[str, Any]:
        """Executa com retry automático."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await asyncio.wait_for(
                    self._execute_once(tool_name, params, context),
                    timeout=timeout
                )
                
                if result.get("success", False):
                    return result
                
                # Se falhou mas não é erro crítico, tenta novamente
                if attempt < max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise
            
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise
        
        raise last_error or Exception("Falha após múltiplas tentativas")
    
    async def _execute_once(self, tool_name: str, params: Dict[str, Any],
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma ferramenta uma vez."""
        tool = self.tool_manager.get_tool(tool_name)
        
        if not tool:
            return {
                "success": False,
                "error": f"Ferramenta não encontrada: {tool_name}"
            }
        
        return await tool.execute_with_validation(params, context)
    
    def _cleanup_executions(self) -> None:
        """Limpa execuções antigas."""
        now = datetime.now()
        to_remove = []
        
        for exec_id, exec_data in self._executions.items():
            started = exec_data.get("started_at")
            if started and (now - started).total_seconds() > 3600:  # 1 hora
                to_remove.append(exec_id)
        
        for exec_id in to_remove:
            del self._executions[exec_id]
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Obtém status de uma execução."""
        return self._executions.get(execution_id)
    
    def get_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtém execuções recentes."""
        sorted_execs = sorted(
            self._executions.items(),
            key=lambda x: x[1].get("started_at", datetime.min),
            reverse=True
        )
        return [
            {
                "id": exec_id,
                **data
            }
            for exec_id, data in sorted_execs[:limit]
        ]