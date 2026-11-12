"""Gerenciador de conhecimento da EVA-OS.

Mantém a interface pública existente e o formato de knowledge_base.json.
Não substitui SemanticMemory ou LongTermMemory.
"""

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any, Dict, List

from src.core.event_types import EventType
from src.kernel.events import EventBus


class KnowledgeManager:
    __plugin_name__ = "knowledge_manager"

    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        self._knowledge_base: Dict[str, Any] = {"facts": {}, "concepts": {}, "categories": {}}
        data_path = self._config_value("paths.data", "./data")
        self._knowledge_path = Path(data_path) / "knowledge" / "knowledge_base.json"
        self._load_base_knowledge()
        self.logger.info("[KnowledgeManager] Inicializado")

    def _config_value(self, key: str, default: Any) -> Any:
        if isinstance(self.config, dict):
            if key in self.config:
                return self.config[key]
            section, _, field = key.partition(".")
            nested = self.config.get(section)
            if isinstance(nested, dict):
                return nested.get(field, default)
        getter = getattr(self.config, "get", None)
        if callable(getter):
            try:
                return getter(key, default)
            except (TypeError, AttributeError):
                pass
        return default

    def _load_base_knowledge(self) -> None:
        """Preserva os dados iniciais do módulo original."""
        self._knowledge_base["facts"] = {
            "brasilia": {"capital": "Brasília", "pais": "Brasil", "inauguracao": 1960,
                         "populacao": "3.4 milhões", "estado": "Distrito Federal", "regiao": "Centro-Oeste"},
            "brasil": {"capital": "Brasília", "idioma": "Português", "moeda": "Real (BRL)",
                       "populacao": "203 milhões", "area": "8.5 milhões km²"},
            "python": {"criador": "Guido van Rossum", "ano": 1991,
                       "tipo": "Linguagem de programação", "paradigma": "Multi-paradigma",
                       "site": "python.org"},
            "eva": {"nome": "EVA OS", "significado": "Evolutionary Virtual Assistant",
                    "versao": "1.0.0", "criador": "Alberto Fernandes"},
        }
        self._knowledge_base["concepts"] = {
            "capital": "Cidade onde está localizada a sede do governo de um país ou estado.",
            "populacao": "Número total de habitantes de uma determinada região.",
            "linguagem_programacao": "Conjunto de regras e sintaxe para escrever programas de computador.",
            "ia": "Inteligência Artificial - área da computação que cria sistemas capazes de aprender e raciocinar.",
        }

    async def initialize(self) -> None:
        self.logger.info("[KnowledgeManager] Inicializando...")
        await self._load_knowledge()
        self._ensure_knowledge_structure()
        self._running = True
        self.logger.info("[KnowledgeManager] Inicializado com %s fatos", len(self._knowledge_base["facts"]))

    def _ensure_knowledge_structure(self) -> None:
        for section in ("facts", "concepts", "categories"):
            if not isinstance(self._knowledge_base.get(section), dict):
                self.logger.warning("[KnowledgeManager] Seção inválida: %s", section)
                self._knowledge_base[section] = {}

    @staticmethod
    def _normalize(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value).casefold())
        return "".join(c for c in text if not unicodedata.combining(c))

    def _extract_keywords(self, message: str) -> List[str]:
        clean = re.sub(r"[^\w\s]", " ", self._normalize(message))
        stopwords = {"a", "o", "e", "de", "da", "do", "que", "com", "para", "por",
                     "um", "uma", "em", "no", "na", "os", "as", "se", "mas", "como",
                     "quando", "onde", "porque", "entao", "isso", "aquilo", "este",
                     "esta", "esses", "essas", "qual", "sua", "seu", "meu", "minha",
                     "nosso", "nossa"}
        result = []
        for word in clean.split():
            if len(word) > 3 and word not in stopwords:
                for term in (word, word[:-1] if word.endswith("s") and len(word) > 4 else word):
                    if term not in result:
                        result.append(term)
        return result

    @staticmethod
    def _entity_names(entities: Any) -> List[str]:
        """Aceita lista do ContextEngine e dicionários legados."""
        names = []
        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict) and isinstance(entity.get("name"), str):
                    names.append(entity["name"])
                elif isinstance(entity, str):
                    names.append(entity)
        elif isinstance(entities, dict):
            if isinstance(entities.get("name"), str):
                names.append(entities["name"])
            else:
                for value in entities.values():
                    if isinstance(value, str):
                        names.append(value)
                    elif isinstance(value, dict) and isinstance(value.get("name"), str):
                        names.append(value["name"])
        return [name.strip() for name in names if name.strip()]

    def _search_facts(self, keywords: List[str]) -> List[Dict[str, Any]]:
        facts = self._knowledge_base.get("facts", {})
        if not isinstance(facts, dict) or not keywords:
            return []
        results = []
        for key, fact in facts.items():
            normalized_key = self._normalize(key)
            score = 1.0 if any(term in normalized_key for term in keywords) else 0.0
            if not score:
                content = json.dumps(fact, ensure_ascii=False, default=str)
                if any(term in self._normalize(content) for term in keywords):
                    score = 0.8
            if score:
                results.append({"type": "fact", "key": key, "data": deepcopy(fact), "relevance": score})
        results.sort(key=lambda item: item["relevance"], reverse=True)
        return results[:5]

    def _search_concepts(self, keywords: List[str]) -> List[Dict[str, Any]]:
        concepts = self._knowledge_base.get("concepts", {})
        if not isinstance(concepts, dict) or not keywords:
            return []
        results = []
        for key, definition in concepts.items():
            key_match = any(term in self._normalize(key) for term in keywords)
            definition_match = any(term in self._normalize(definition) for term in keywords)
            if key_match or definition_match:
                results.append({"type": "concept", "key": key,
                                "definition": deepcopy(definition),
                                "relevance": 1.0 if key_match else 0.7})
        results.sort(key=lambda item: item["relevance"], reverse=True)
        return results[:3]

    def _search_entities(self, entities: Any) -> List[Dict[str, Any]]:
        facts = self._knowledge_base.get("facts", {})
        if not isinstance(facts, dict):
            return []
        results = []
        seen = set()
        for name in self._entity_names(entities):
            needle = self._normalize(name)
            for key, fact in facts.items():
                if key not in seen and needle in self._normalize(key):
                    results.append({"type": "entity", "entity_type": "name",
                                    "entity_value": name, "data": deepcopy(fact), "relevance": 1.0})
                    seen.add(key)
        return results[:3]

    def query(self, text: str) -> Dict[str, Any] | None:
        """Responde apenas perguntas factuais explícitas, com entidade e campo exatos.

        Uma correspondência de palavras-chave não constitui resposta confiável.
        Retorna None em casos ambíguos, compostos ou sem dados.
        """
        if not isinstance(text, str) or not text.strip():
            return None
        question = self._normalize(text)
        question = re.sub(r"[^\w\s]", " ", question)
        question = " ".join(question.split())
        # 'EVA' como vocativo não é a entidade consultada.
        question = re.sub(r"^eva\s+", "", question)

        patterns = (
            (r"(?:quem criou|quem e o criador (?:de|do|da)) (.+)", "criador", "{entity} foi criado por {value}."),
            (r"qual (?:e )?o criador (?:de|do|da) (.+)", "criador", "{entity} foi criado por {value}."),
            (r"qual (?:e )?a capital (?:de|do|da) (.+)", "capital", "A capital de {entity} é {value}."),
            (r"qual (?:e )?o significado (?:de|do|da) (.+)", "significado", "O significado de {entity} é {value}."),
            (r"(?:em que ano|qual ano) (.+) foi (?:criado|criada)", "ano", "{entity} foi criado em {value}."),
            (r"qual (?:e )?a moeda (?:de|do|da) (.+)", "moeda", "A moeda de {entity} é {value}."),
            (r"qual (?:e )?o idioma (?:de|do|da) (.+)", "idioma", "O idioma de {entity} é {value}."),
        )
        facts = self._knowledge_base.get("facts", {})
        if not isinstance(facts, dict):
            return None
        for pattern, field, template in patterns:
            match = re.fullmatch(pattern, question)
            if not match:
                continue
            requested = match.group(1).strip()
            if field == "criador":
                requested = re.sub(r"^(?:o|a)\s+", "", requested)
            candidates = [(key, record) for key, record in facts.items()
                          if self._normalize(key) == requested and isinstance(record, dict)]
            if len(candidates) != 1:
                return None
            key, record = candidates[0]
            value = record.get(field)
            if not isinstance(value, (str, int, float)) or isinstance(value, bool) or not str(value).strip():
                return None
            display = "EVA" if key == "eva" else key.capitalize()
            if key == "brasil" and field in {"capital", "moeda", "idioma"}:
                display = "do Brasil"
                template = template.replace("de {entity}", "{entity}")
            return {"answer": template.format(entity=display, value=value),
                    "confidence": 1.0, "resolved": True,
                    "source": "knowledge_base", "fact_key": key, "field": field}
        return None

    async def process(self, context: Dict[str, Any], memory: Dict[str, Any] = None) -> Dict[str, Any]:
        if not isinstance(context, dict):
            self.logger.warning("[KnowledgeManager] Contexto inválido; usando contexto vazio")
            context = {}
        message = context.get("message", "")
        if not isinstance(message, str):
            message = str(message) if message is not None else ""
        keywords = self._extract_keywords(message)
        entities = context.get("entities")
        if not entities and isinstance(context.get("state"), dict):
            entities = context["state"].get("active_entities", [])
        facts = self._search_facts(keywords)
        concepts = self._search_concepts(keywords)
        entity_knowledge = self._search_entities(entities)
        result = {"keywords": keywords, "facts": facts, "concepts": concepts,
                  "entity_knowledge": entity_knowledge,
                  "total_results": len(facts) + len(concepts) + len(entity_knowledge),
                  "timestamp": datetime.now().isoformat()}
        if self.event_bus is not None:
            await self.event_bus.publish_async(
                EventType.KNOWLEDGE_QUERIED,
                {"context": context, "memory": memory or {}, "knowledge": result,
                 "timestamp": datetime.now().isoformat()},
                source="knowledge_manager",
            )
        return result

    async def add_knowledge(self, key: str, data: Dict[str, Any], category: str = "facts") -> bool:
        if not isinstance(key, str) or not key.strip() or category not in ("facts", "concepts", "categories"):
            self.logger.warning("[KnowledgeManager] Chave ou categoria inválida")
            return False
        if not isinstance(data, (dict, str, list, int, float, bool)) and data is not None:
            self.logger.warning("[KnowledgeManager] Tipo de conhecimento inválido")
            return False
        section = self._knowledge_base.get(category)
        if not isinstance(section, dict):
            self.logger.error("[KnowledgeManager] Categoria corrompida: %s", category)
            return False
        key = key.strip()
        existed = key in section
        previous = deepcopy(section.get(key))
        section[key] = deepcopy(data)
        if not await self._save_knowledge():
            if existed:
                section[key] = previous
            else:
                section.pop(key, None)
            return False
        self.logger.info("[KnowledgeManager] Conhecimento adicionado: %s", key)
        return True

    async def _load_knowledge(self) -> None:
        if not self._knowledge_path.exists():
            return
        try:
            with self._knowledge_path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError("O arquivo de conhecimento não contém um objeto JSON")
            for section in ("facts", "concepts", "categories"):
                value = loaded.get(section)
                if value is None:
                    continue
                if isinstance(value, dict):
                    self._knowledge_base[section].update(value)
                else:
                    self.logger.warning("[KnowledgeManager] Ignorando seção inválida: %s", section)
            self.logger.info("[KnowledgeManager] Conhecimento persistido carregado")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.logger.error("[KnowledgeManager] Falha ao carregar %s: %s", self._knowledge_path, exc)

    async def _save_knowledge(self) -> bool:
        temp_path = None
        try:
            self._knowledge_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._knowledge_path.parent,
                                             prefix=".knowledge_", suffix=".tmp", delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(self._knowledge_base, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._knowledge_path)
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.logger.error("[KnowledgeManager] Falha ao salvar conhecimento: %s", exc)
            return False
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    async def shutdown(self) -> None:
        self.logger.info("[KnowledgeManager] Desligando...")
        if not await self._save_knowledge():
            self.logger.error("[KnowledgeManager] Não foi possível persistir a base no desligamento")
        self._running = False

    async def health_check(self) -> dict:
        return {"status": "running" if self._running else "stopped",
                "facts": len(self._knowledge_base.get("facts", {})),
                "concepts": len(self._knowledge_base.get("concepts", {}))}
