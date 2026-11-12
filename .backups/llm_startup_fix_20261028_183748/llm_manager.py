"""Gerenciador de geração via Ollama para EVA-OS.

O histórico e o contexto são preparados pelo Brain/PromptBuilder. Este módulo
não guarda conversas entre chamadas para evitar duplicação e mistura de usuários.
"""
import asyncio
from typing import Any, Dict, List, Optional
import aiohttp
from src.kernel.events import EventBus


class LLMManager:
    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._ollama_host = config.get("llm.ollama.host", "localhost")
        self._ollama_port = config.get("llm.ollama.port", 11434)
        self._model = config.get("llm.model", "qwen2.5:7b")
        self._running = False
        # Mantido por compatibilidade com consumidores que consultem o atributo.
        self._conversation_history: List[Dict[str, str]] = []
        self.logger.info(f"LLMManager configurado com modelo: {self._model}")

    def _base_url(self) -> str:
        host = str(self._ollama_host).rstrip("/")
        if host.startswith(("http://", "https://")):
            return host if host.rsplit(":", 1)[-1].isdigit() else f"{host}:{self._ollama_port}"
        return f"http://{host}:{self._ollama_port}"

    async def initialize(self) -> None:
        self.logger.info("LLMManager inicializando...")
        self._running = True
        if not await self._check_ollama():
            self.logger.warning("Ollama não disponível na inicialização")
        else:
            models = await self._get_available_models()
            if models and self._model not in models:
                self.logger.warning(
                    f"Modelo configurado '{self._model}' não encontrado. "
                    f"Disponíveis: {', '.join(models)}. Não trocando automaticamente."
                )
        self.logger.info(f"LLMManager inicializado com modelo: {self._model}")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            return "Não recebi uma mensagem válida para processar."
        url = f"{self._base_url()}/api/chat"
        data = {
            "model": self._model,
            "messages": self._build_messages(prompt, system_prompt),
            "stream": False,
            "options": {"temperature": 0.8, "top_p": 0.9, "num_predict": 1024},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        details = (await resp.text())[:300]
                        self.logger.error(f"Ollama HTTP {resp.status}: {details}")
                        return self._fallback_response(prompt)
                    result = await resp.json()

                    # Metricas de desempenho retornadas pelo Ollama
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
                        f"Geracao: {eval_time:.2f}s ({generated_tokens} tokens) | "
                        f"Velocidade: {speed:.2f} tokens/s"
                    )

                    answer = result.get("message", {}).get("content", "")
                    if isinstance(answer, str) and answer.strip():
                        return answer.strip()
                    self.logger.warning("Ollama retornou resposta vazia")
                    return self._fallback_response(prompt)
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            self.logger.error("Timeout ao aguardar resposta do Ollama")
            return "Desculpe, o modelo demorou demais para responder. Pode tentar novamente?"
        except (aiohttp.ClientError, OSError, ValueError) as exc:
            self.logger.error(f"Falha na comunicação com Ollama: {exc}")
            return self._fallback_response(prompt)

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        system = system_prompt if system_prompt is not None else (
            "Você é EVA, uma assistente virtual familiar. Responda em português "
            "brasileiro com clareza, naturalidade e respeito. Não invente fatos "
            "sobre pessoas ou sobre a família; quando não souber, diga isso."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

    def _fallback_response(self, prompt: str) -> str:
        return "Desculpe, não consegui processar sua mensagem agora. Pode repetir, por favor?"

    async def _check_ollama(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url()}/api/tags", timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    async def _get_available_models(self) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url()}/api/tags", timeout=aiohttp.ClientTimeout(total=3)
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
        self.logger.info("Histórico interno do LLM limpo (contexto gerenciado pelo Brain)")

    async def shutdown(self) -> None:
        self._running = False
        self.logger.info("LLMManager desligado")

    async def health_check(self) -> dict:
        return {
            "running": self._running,
            "model": self._model,
            "ollama_available": await self._check_ollama(),
            "history_size": 0,
        }
