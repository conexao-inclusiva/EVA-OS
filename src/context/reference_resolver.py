# -*- coding: utf-8 -*-
"""Resolução conservadora de referências no contexto da conversa da EVA."""

import inspect
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional


class ReferenceResolver:
    """Resolve referências usando entidades, tópicos e histórico disponível."""

    _PATTERNS = (
        (r"\b(?:aquele|aquela|esse|essa|esses|essas|aqueles|aquelas)\s+(?:projeto|negócio|computador|pc|servidor|carro|veículo|sistema|ideia|coisa)\b", "entity_ref"),
        (r"\b(?:o\s+que|qual)\s+falamos\s+antes\b", "previous_ref"),
        (r"\ba\s+qual\s+você\s+mencionou\b", "mentioned_ref"),
        (r"\baquele\s+que\s+eu\s+falei\s+antes\b", "mentioned_ref"),
        (r"\b(?:ele|ela|eles|elas|dele|dela|deles|delas)\b", "pronoun"),
        (r"\b(?:isso|isto|aquilo|esse|essa|esses|essas|aquele|aquela|aqueles|aquelas)\b", "demonstrative"),
        (r"\b(?:outro|outra)\b", "other"),
    )

    _TYPE_HINTS = {
        "carro": ("car", "vehicle", "veiculo", "veículo", "automovel", "automóvel"),
        "veículo": ("car", "vehicle", "veiculo", "veículo", "automovel", "automóvel"),
        "projeto": ("project", "projeto"),
        "servidor": ("server", "servidor"),
        "computador": ("computer", "computador", "pc"),
        "pc": ("computer", "computador", "pc"),
        "sistema": ("system", "sistema"),
        "ideia": ("idea", "ideia"),
    }

    def __init__(self):
        self.logger = None
        self._confidence_threshold = 0.6
        self._pronouns = {
            "ele": ["ele", "ela", "eles", "elas"],
            "isso": ["isso", "isto", "aquilo"],
            "esse": ["esse", "essa", "esses", "essas"],
            "aquele": ["aquele", "aquela", "aqueles", "aquelas"],
            "outro": ["outro", "outra"],
        }

    def set_logger(self, logger):
        self.logger = logger

    @staticmethod
    def _clean_entities(entities):
        return [item for item in (entities or []) if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()]

    def resolve(self, text: str, entities: List[Dict], topics: List[str],
                recent_messages: List[str], context: Dict = None) -> Dict[str, Any]:
        result = {"references": {}, "unresolved": [], "confidence": {}}
        if not isinstance(text, str) or not text.strip():
            return result
        entities = self._clean_entities(entities)
        topics = [t for t in (topics or []) if isinstance(t, str) and t.strip()]
        recent_messages = [m for m in (recent_messages or []) if isinstance(m, str)]
        context = context if isinstance(context, dict) else {}
        occupied = []
        for pattern, ref_type in self._PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                occupied.append(match.span())
                phrase = match.group(0)
                candidate = self._resolve_reference(phrase, ref_type, entities, topics, recent_messages, context)
                if candidate and candidate.get("confidence", 0) >= self._confidence_threshold:
                    result["references"][phrase] = deepcopy(candidate["entity"])
                    result["confidence"][phrase] = candidate["confidence"]
                else:
                    result["unresolved"].append(phrase)
        return result

    def _resolve_reference(self, ref_text: str, ref_type: str,
                           entities: List[Dict], topics: List[str],
                           recent_messages: List[str], context: Dict) -> Optional[Dict]:
        ref = ref_text.casefold().strip()
        candidates = self._clean_entities(entities)
        if isinstance(context, dict):
            previous = context.get("last_entity")
            if isinstance(previous, dict) and previous.get("name"):
                if not any(e.get("name", "").casefold() == str(previous["name"]).casefold() for e in candidates):
                    candidates.append(previous)

        # A referência nominal precisa identificar inequivocamente uma entidade.
        if ref_type == "entity_ref":
            noun = ref.split()[-1]
            matching = []
            for entity in candidates:
                name = str(entity.get("name", "")).casefold()
                kind = str(entity.get("type", "")).casefold()
                aliases = [str(a).casefold() for a in (entity.get("aliases") or []) if isinstance(a, str)]
                hints = self._TYPE_HINTS.get(noun, (noun,))
                if noun in name.split() or noun in aliases or kind in hints:
                    matching.append(entity)
            if len(matching) == 1:
                return {"entity": matching[0], "confidence": 0.85}
            return None

        # Pronomes não devem ser associados arbitrariamente à primeira entidade.
        if ref_type == "pronoun":
            if len(candidates) == 1:
                return {"entity": candidates[0], "confidence": 0.7}
            return None

        if ref_type in ("previous_ref", "mentioned_ref"):
            for msg in reversed(recent_messages[-5:]):
                extracted = self._extract_entities_from_text(msg)
                if len(extracted) == 1:
                    return {"entity": extracted[0], "confidence": 0.65}
            if len(candidates) == 1:
                return {"entity": candidates[0], "confidence": 0.65}
            return None

        if ref_type == "demonstrative":
            if len(candidates) == 1:
                return {"entity": candidates[0], "confidence": 0.65}
            if not candidates and len(topics) == 1:
                return {"entity": {"name": topics[0], "type": "topic"}, "confidence": 0.6}
        return None

    def _extract_entities_from_text(self, text: str) -> List[Dict]:
        if not isinstance(text, str):
            return []
        patterns = (
            (r"\b(?:Arduino|Raspberry|ESP32|Jellyfin|MikroTik|Windows|Linux)\b", "tech_name"),
            (r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)*\b", "proper_name"),
        )
        found = {}
        for pattern, kind in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(0)
                if len(name) > 2:
                    found.setdefault(name.casefold(), {"name": name, "type": kind, "source": "extracted"})
        return list(found.values())

    def resolve_with_llm(self, ref_text: str, llm_manager) -> Optional[Dict]:
        """Fallback somente para geradores síncronos. Para async, use resolve_with_llm_async."""
        if not llm_manager or not callable(getattr(llm_manager, "generate", None)):
            return None
        if inspect.iscoroutinefunction(llm_manager.generate):
            if self.logger:
                self.logger.warning("ReferenceResolver: generate é async; use resolve_with_llm_async")
            return None
        try:
            response = llm_manager.generate(self._llm_prompt(ref_text))
            return self._llm_result(response)
        except Exception as exc:
            if self.logger:
                self.logger.warning("ReferenceResolver: falha no fallback LLM: %s", exc)
            return None

    async def resolve_with_llm_async(self, ref_text: str, llm_manager) -> Optional[Dict]:
        """Fallback assíncrono compatível com LLMManager.generate coroutine."""
        if not llm_manager or not callable(getattr(llm_manager, "generate", None)):
            return None
        try:
            response = llm_manager.generate(self._llm_prompt(ref_text))
            if inspect.isawaitable(response):
                response = await response
            return self._llm_result(response)
        except Exception as exc:
            if self.logger:
                self.logger.warning("ReferenceResolver: falha no fallback LLM: %s", exc)
            return None

    @staticmethod
    def _llm_prompt(ref_text: str) -> str:
        return ("Identifique a entidade referida apenas se o contexto permitir. "
                "Se não houver contexto suficiente, responda DESCONHECIDO. "
                "Responda apenas com o nome da entidade.\nTexto: " + str(ref_text))

    @staticmethod
    def _llm_result(response) -> Optional[Dict]:
        if not isinstance(response, str):
            return None
        name = response.strip()
        if not name or len(name) >= 50 or name.casefold() in ("desconhecido", "não sei", "nao sei", "nenhum"):
            return None
        return {"entity": {"name": name, "type": "resolved"}, "confidence": 0.6}

    def get_confidence_threshold(self) -> float:
        return self._confidence_threshold

    def set_confidence_threshold(self, threshold: float) -> None:
        if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            raise ValueError("threshold deve estar entre 0 e 1")
        self._confidence_threshold = float(threshold)
