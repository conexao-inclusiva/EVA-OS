"""Extrator de conhecimento."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re


class KnowledgeExtractor:
    """
    Extrai conhecimento de conversas e interações.
    """
    
    def __init__(self, learning_manager):
        self.learning_manager = learning_manager
        self.logger = learning_manager.logger
        self.knowledge_manager = learning_manager.knowledge_manager
        
        self._extracted: List[Dict[str, Any]] = []
    
    async def extract_from_text(self, text: str, source: str = "unknown") -> List[Dict[str, Any]]:
        """
        Extrai conhecimento de um texto.
        """
        knowledge = []
        
        # 1. Extrai definições
        definitions = self._extract_definitions(text)
        for concept, definition in definitions:
            knowledge.append({
                "type": "definition",
                "concept": concept,
                "description": definition,
                "source": source
            })
        
        # 2. Extrai fatos
        facts = self._extract_facts(text)
        for fact in facts:
            knowledge.append({
                "type": "fact",
                "concept": fact["subject"],
                "description": fact["predicate"],
                "source": source
            })
        
        # 3. Extrai procedimentos
        procedures = self._extract_procedures(text)
        for procedure in procedures:
            knowledge.append({
                "type": "procedure",
                "name": procedure["name"],
                "steps": procedure["steps"],
                "source": source
            })
        
        # Armazena no KnowledgeManager
        for item in knowledge:
            if item["type"] == "definition":
                await self.knowledge_manager._on_add(
                    self._create_event({
                        "concept": item["concept"],
                        "description": item["description"],
                        "source": item["source"],
                        "confidence": 0.5
                    })
                )
        
        self._extracted.extend(knowledge)
        return knowledge
    
    async def extract_from_dict(self, data: Dict[str, Any], source: str = "unknown") -> List[Dict[str, Any]]:
        """
        Extrai conhecimento de um dicionário.
        """
        knowledge = []
        
        if "concept" in data and "description" in data:
            knowledge.append({
                "type": "definition",
                "concept": data["concept"],
                "description": data["description"],
                "source": source
            })
        
        if "facts" in data:
            for fact in data["facts"]:
                knowledge.append({
                    "type": "fact",
                    "concept": fact.get("subject", ""),
                    "description": fact.get("predicate", ""),
                    "source": source
                })
        
        return knowledge
    
    async def extract(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retorna conhecimento extraído recentemente.
        """
        return self._extracted[-limit:]
    
    def _extract_definitions(self, text: str) -> List[tuple]:
        """
        Extrai definições no formato "X é Y".
        """
        definitions = []
        
        # Padrões: "X é Y" ou "X significa Y" ou "X é quando Y"
        patterns = [
            r'([A-Za-zÀ-ÿ\s]{2,30})\s+[ée]\s+([A-Za-zÀ-ÿ\s,;]{5,100})',
            r'([A-Za-zÀ-ÿ\s]{2,30})\s+significa\s+([A-Za-zÀ-ÿ\s,;]{5,100})',
            r'([A-Za-zÀ-ÿ\s]{2,30})\s+[ée]\s+quando\s+([A-Za-zÀ-ÿ\s,;]{5,100})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                concept = match[0].strip()
                definition = match[1].strip()
                if len(concept) > 2 and len(definition) > 10:
                    definitions.append((concept, definition))
        
        return definitions[:3]
    
    def _extract_facts(self, text: str) -> List[Dict[str, str]]:
        """
        Extrai fatos no formato "X é Y" ou "X tem Y".
        """
        facts = []
        
        patterns = [
            r'([A-Za-zÀ-ÿ\s]{2,30})\s+[ée]\s+([A-Za-zÀ-ÿ\s,;]{3,50})',
            r'([A-Za-zÀ-ÿ\s]{2,30})\s+tem\s+([A-Za-zÀ-ÿ\s,;]{3,50})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                facts.append({
                    "subject": match[0].strip(),
                    "predicate": match[1].strip()
                })
        
        return facts[:5]
    
    def _extract_procedures(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrai procedimentos (passos).
        """
        procedures = []
        
        # Detecta listas de passos
        if "primeiro" in text and "depois" in text:
            steps = re.findall(r'(?:primeiro|depois|em seguida|então|finalmente)\s+([A-Za-zÀ-ÿ\s,;]{5,50})', text)
            if steps:
                procedures.append({
                    "name": "Procedimento extraído",
                    "steps": steps
                })
        
        return procedures
    
    def _create_event(self, data: Dict[str, Any]) -> Any:
        """Cria um evento para o KnowledgeManager."""
        from src.kernel.events import Event
        return Event(
            type="knowledge.add",
            payload=data,
            source="knowledge_extractor"
        )