"""Resolvedor de dependências entre tarefas."""

from typing import List, Dict, Set, Optional
from collections import defaultdict

from src.planner.task import Task


class DependencyResolver:
    """
    Resolve dependências entre tarefas.
    Implementa ordenação topológica.
    """
    
    def resolve(self, tasks: List[Task]) -> List[Task]:
        """
        Resolve dependências entre tarefas.
        Retorna tarefas com dependências resolvidas (ordenadas).
        """
        if not tasks:
            return tasks
        
        # Cria grafo de dependências
        graph = defaultdict(set)
        in_degree = defaultdict(int)
        
        for task in tasks:
            graph[task.id] = set()
            in_degree[task.id] = 0
        
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in graph:
                    graph[dep_id].add(task.id)
                    in_degree[task.id] += 1
        
        # Ordenação topológica (Kahn)
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            task_id = queue.pop(0)
            result.append(task_id)
            
            for neighbor in graph[task_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Verifica ciclos
        if len(result) != len(tasks):
            # Há ciclo - tenta resolver
            unresolved = set(t.id for t in tasks) - set(result)
            self.logger.warning(f"Ciclo de dependência detectado: {unresolved}")
            
            # Adiciona os não resolvidos no final
            result.extend(unresolved)
        
        # Reordena tarefas
        task_map = {t.id: t for t in tasks}
        return [task_map[tid] for tid in result if tid in task_map]
    
    def detect_cycles(self, tasks: List[Task]) -> List[List[str]]:
        """
        Detecta ciclos no grafo de dependências.
        Retorna lista de ciclos encontrados.
        """
        graph = defaultdict(set)
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in {t.id for t in tasks}:
                    graph[task.id].add(dep_id)
        
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node_id: str, path: List[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            for neighbor in graph[node_id]:
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Ciclo encontrado
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node_id)
        
        for task in tasks:
            if task.id not in visited:
                dfs(task.id, [])
        
        return cycles