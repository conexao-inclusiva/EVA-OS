# -*- coding: utf-8 -*-
"""Gerenciador de geração via Ollama para EVA-OS com suporte a execução offline, semaphore de concorrência e otimização de GPU/threading.

O histórico e o contexto são preparados pelo Brain/PromptBuilder. Este módulo
prioriza a execução de LLMs locais via Ollama/endpoints e fornece execução
fallback offline confiável sem travamentos de conexão.
"""
import asyncio
from typing import Any, Dict, List, Optional
import aiohttp
from src.kernel.events import EventBus
from src.core.llm_decision_gate import LLMDecisionGate


class LLMManager:
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._ollama_host = config.get("llm.ollama.host", "localhost")
        self._ollama_port = config.get("llm.ollama.port", 11434)
        self._model = config.get("llm.model", "qwen2.5:7b")
        
        # Otimizações para GPU e CPU para evitar pico de 100%
        self._num_gpu = config.get("llm.ollama.num_gpu", config.get("llm.num_gpu", 1))
        self._num_thread = config.get("llm.ollama.num_thread", config.get("llm.num_thread", 4))
        
        # Asyncio Semaphore para limitar chamadas concorrentes ao LLM
        max_concurrent = config.get("llm.max_concurrent", 1)
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Cache simples para requisições não essenciais (prompt -> resposta)
        self._cache: Dict[str, str] = {}

        self._running = False
        self._ollama_available = False
        # Mantido por compatibilidade com consumidores que consultem o atributo.
        self._conversation_history: List[Dict[str, str]] = []
        self.decision_gate = LLMDecisionGate(logger)
        self.logger.info(
            f"LLMManager configurado com modelo: {self._model} "
            f"(num_gpu={self._num_gpu}, num_thread={self._num_thread}, max_concurrent={max_concurrent})"
        )

    def _base_url(self) -> str:
        host = str(self._ollama_host).rstrip("/")
        if host.startswith(("http://", "https://")):
            return host if host.rsplit(":", 1)[-1].isdigit() else f"{host}:{self._ollama_port}"
        return f"http://{host}:{self._ollama_port}"

    @property
    def is_available(self) -> bool:
        return self._ollama_available

    async def initialize(self) -> None:
        self.logger.info("LLMManager inicializando...")
        self._running = True

        for tentativa in range(1, 4):
            if await self._check_ollama():
                self._ollama_available = True
                break

            if tentativa < 3:
                self.logger.warning(
                    f"Ollama indisponível em {self._base_url()} "
                    f"(tentativa {tentativa}/3). Nova tentativa em 1 segundo."
                )
                await asyncio.sleep(1)
        else:
            self._ollama_available = False
            self.logger.warning(
                f"Ollama local não respondeu em {self._base_url()}. "
                "LLMManager operando com modo de execução e fallback offline ativado."
            )

        if self._ollama_available:
            models = await self._get_available_models()
            if models and self._model not in models:
                self.logger.warning(
                    f"Modelo configurado '{self._model}' não encontrado. "
                    f"Disponíveis: {', '.join(models)}. Não trocando automaticamente."
                )
            self.logger.info(f"LLMManager inicializado com modelo: {self._model}")
        else:
            self.logger.info("LLMManager inicializado em modo offline.")

    async def should_call_llm(
        self, context: Dict, local_resolution: Optional[Dict] = None
    ) -> bool:
        """Integração com LLMDecisionGate para determinar se o LLM deve ser invocado."""
        return await self.decision_gate.should_call_llm(context, local_resolution)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        local_resolution: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            return "Não recebi uma mensagem válida para processar."

        if context is not None:
            if not await self.should_call_llm(context, local_resolution):
                local_resp = (
                    local_resolution.get("response") if local_resolution
                    else context.get("local_response")
                )
                if local_resp:
                    return str(local_resp).strip()

        # Verifica cache para requisições não essenciais/repetidas
        cache_key = f"{system_prompt or ''}:{prompt}"
        if use_cache and cache_key in self._cache:
            self.logger.debug("[LLMManager] Retornando resposta do cache para otimização de carga")
            return self._cache[cache_key]

        if not self._ollama_available:
            if not await self._check_ollama():
                return self._fallback_response(prompt)
            self._ollama_available = True

        url = f"{self._base_url()}/api/chat"
        data = {
            "model": self._model,
            "messages": self._build_messages(prompt, system_prompt),
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 1024,
                "num_gpu": self._num_gpu,
                "num_thread": self._num_thread,
            },
        }
        # ✅ MODIFICAÇÃO AQUI — Tempo limite aumentado de 45s para 180s
        timeout = aiohttp.ClientTimeout(total=180, connect=5.0)
        
        async with self._semaphore:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=data) as resp:
                        if resp.status != 200:
                            details = (await resp.text())[:300]
                            self.logger.error(f"Ollama HTTP {resp.status}: {details}")
                            self._ollama_available = False
                            return self._fallback_response(prompt)
                        result = await resp.json()

                        # Métricas de desempenho retornadas pelo Ollama
                        total = result.get("total_duration", 0) / 1e9
                        load = result.get("load_duration", 0) / 1e9
                        prompt_time = result.get("prompt_eval_duration", 0) / 1e9
                        eval_time = result.get("eval_duration", 0) / 1e9
                        prompt_tokens = result.get("prompt_eval_count", 0)
                        generated_tokens = result.get("eval_count", 0)
                        speed = generated_tokens / eval_time if eval_time > 0 else 0

                        self.logger.info(
                            f"[LLM METRICAS] Total: {total:.2f}s | "
                            f"Carregamento: {load:.2f}s | "
                            f"Prompt: {prompt_time:.2f}s ({prompt_tokens} tokens) | "
                            f"Geração: {eval_time:.2f}s ({generated_tokens} tokens) | "
                            f"Velocidade: {speed:.2f} tokens/s"
                        )

                        answer = result.get("message", {}).get("content", "")
                        if isinstance(answer, str) and answer.strip():
                            cleaned = answer.strip()
                            if use_cache:
                                self._cache[cache_key] = cleaned
                            return cleaned
                        self.logger.warning("Ollama retornou resposta vazia")
                        return self._fallback_response(prompt)
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                self.logger.error("Timeout ao aguardar resposta do Ollama (offline ou lento)")
                self._ollama_available = False
                return self._fallback_response(prompt)
            except (aiohttp.ClientError, OSError, ValueError) as exc:
                self.logger.error(f"Falha na comunicação com Ollama: {exc}")
                self._ollama_available = False
                return self._fallback_response(prompt)

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        system = system_prompt if system_prompt is not None else (
            "Você é EVA, uma assistente pessoal e companheira atenta inspirada no Baymax. "
            "Responda em português brasileiro com tom acolhedor, calmo, claro e cuidadoso. "
            "Não invente fatos sobre pessoas ou sobre a família; quando não souber, diga isso claramente."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

    def _fallback_response(self, prompt: str) -> str:
        return (
            "Estou operando em modo offline no momento. O modelo de linguagem local "
            "não está disponível, mas continuo ativo para cuidar do seu bem-estar e auxiliar com os dados locais."
        )

    async def _check_ollama(self) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=2.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self._base_url()}/api/tags"
                ) as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    async def _get_available_models(self) -> List[str]:
        try:
            timeout = aiohttp.ClientTimeout(total=2.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self._base_url()}/api/tags"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return [m["name"] for m in data.get("models", [])
                                if isinstance(m, dict) and isinstance(m.get("name"), str)]
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
            self.logger.warning(f"Não foi possível listar modelos: {exc}")
        return []

    def clear_history(self) -> None:
        self._conversation_history.clear()
        self._cache.clear()
        self.logger.info("Histórico interno e cache do LLM limpos (contexto gerenciado pelo Brain)")

    async def shutdown(self) -> None:
        self._running = False
        self._ollama_available = False
        self._cache.clear()
        self.logger.info("LLMManager desligado")

    async def health_check(self) -> dict:
        available = await self._check_ollama()
        self._ollama_available = available
        return {
            "running": self._running,
            "model": self._model,
            "ollama_available": available,
            "offline_mode": not available,
            "history_size": 0,
            "cache_size": len(self._cache),
            "num_gpu": self._num_gpu,
            "num_thread": self._num_thread,
            "gate_stats": self.decision_gate.get_stats(),
        }
