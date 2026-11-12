# -*- coding: utf-8 -*-
"""Decide quando uma resposta local comprovada dispensa o LLM.

A presença de entidades, tópicos ou memórias NÃO comprova que exista uma
resposta. Por segurança, sem uma resposta local explícita o LLM é solicitado.
"""

from typing import Any, Dict, Optional
import math


class LLMDecisionGate:
    """Portão de decisão compatível com Brain.should_call_llm(context)."""

    def __init__(self, logger):
        self.logger = logger
        self._local_cognition_count = 0
        self._llm_call_count = 0

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            confidence = float(value)
            return confidence if math.isfinite(confidence) else 0.0
        except (TypeError, ValueError, OverflowError):
            return 0.0

    async def should_call_llm(
        self, context: Dict,
        local_resolution: Optional[Dict] = None,
    ) -> bool:
        """Retorna False somente com resposta local explícita e confiável.

        local_resolution pode conter `response` ou `answer` (texto não vazio),
        `confidence` (0..1) e opcionalmente `resolved` (False impede uso).
        O Brain atualmente chama este método sem local_resolution; nesse caso
        a decisão conservadora é True, sem alterar o contrato existente.
        """
        data = self._as_dict(context)
        local = self._as_dict(local_resolution)
        unresolved = data.get("unresolved_references")
        if not unresolved:
            state = self._as_dict(data.get("state"))
            unresolved = state.get("unresolved_references")

        answer = local.get("response")
        if not isinstance(answer, str) or not answer.strip():
            answer = local.get("answer")
        has_answer = isinstance(answer, str) and bool(answer.strip())
        confidence = self._confidence(local.get("confidence"))

        if not unresolved and has_answer and confidence >= 0.8 and local.get("resolved") is not False:
            self._local_cognition_count += 1
            self._log("Resolução local com resposta e confiança suficientes → sem LLM")
            return False

        self._llm_call_count += 1
        self._log("Sem resposta local comprovada ou há referência pendente → LLM")
        return True

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.debug("[DecisionGate] %s", message)

    def get_stats(self) -> Dict:
        """Estatísticas de decisões tomadas, não de respostas concluídas."""
        total = self._local_cognition_count + self._llm_call_count
        return {
            "local_cognition_count": self._local_cognition_count,
            "llm_call_count": self._llm_call_count,
            "local_cognition_rate": self._local_cognition_count / total if total else 0,
            "total_requests": total,
        }
