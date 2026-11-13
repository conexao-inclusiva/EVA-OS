"""Gerenciador de Memória - FASE 2 do pipeline cognitivo da EVA."""

import asyncio
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from src.core.event_types import EventType
from src.kernel.events import EventBus


class MemoryManager:
    """
    Mantém histórico e preferências por usuário, com persistência em JSON,
    backup automático e política de retenção para manter memória limpa.
    """

    # === CONFIGURAÇÕES DE RETENÇÃO ===
    MAX_MESSAGES_PER_USER = 50         # Máximo de mensagens por usuário
    MAX_CONVERSATION_AGE_DAYS = 30      # Arquiva conversas mais antigas que 30 dias
    RECENT_CONTEXT_LIMIT = 10           # Quantas mensagens aparecem no contexto atual

    def __init__(self, event_bus: EventBus, logger, config):
        self.event_bus = event_bus
        self.logger = logger
        self.config = config
        self._running = False
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        self._preferences: Dict[str, Dict[str, Any]] = {}
        self._save_lock = asyncio.Lock()

        # Compatível tanto com KernelConfig.get('paths.data') quanto com
        # configurações fornecidas como dicionário aninhado.
        data_dir = None
        if hasattr(config, "get"):
            try:
                data_dir = config.get("paths.data", None)
            except (TypeError, AttributeError):
                pass
            if isinstance(config, dict):
                data_dir = config.get("paths", {}).get("data", data_dir) if isinstance(config.get("paths"), dict) else data_dir
        data_dir = data_dir if isinstance(data_dir, (str, os.PathLike)) and data_dir else "./data"
        data_path = Path(data_dir)
        self._memory_path = data_path / "memory" / "conversations.json"
        self._preferences_path = data_path / "memory" / "preferences.json"
        self._logger_prefix = "🧠 [MemoryManager]"
        self.logger.info(f"{self._logger_prefix} Inicializado | Retenção: {self.MAX_MESSAGES_PER_USER} msg / {self.MAX_CONVERSATION_AGE_DAYS} dias")

    def _make_backup(self, filepath: Path) -> bool:
        """Cria um backup do arquivo antes de sobrescrever. Retorna True se sucesso."""
        if filepath.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = filepath.with_name(f"{filepath.name}.{timestamp}.bak")
            try:
                shutil.copy2(filepath, backup_path)
                self.logger.info(f"💾 Backup criado: {backup_path}")
                return True
            except Exception as e:
                self.logger.warning(f"⚠️ Não foi possível criar backup de {filepath}: {e}")
        return False

    def _cleanup_old_memories(self, user_id: str) -> int:
        """
        Aplica política de retenção:
        - Remove mensagens mais antigas se passar do limite
        - Marca conversas antigas demais como arquivadas
        Retorna o número de mensagens removidas.
        """
        history = self._conversations.get(str(user_id), [])
        if not history:
            return 0

        original_count = len(history)
        now = datetime.now()

        # 1. Filtrar mensagens dentro do prazo de validade
        valid_messages = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            ts_str = entry.get("timestamp")
            try:
                ts = datetime.fromisoformat(str(ts_str)) if ts_str else now
                age = now - ts
                if age.days <= self.MAX_CONVERSATION_AGE_DAYS:
                    valid_messages.append(entry)
                else:
                    self.logger.debug(f"{self._logger_prefix} Mensagem arquivada por idade: {ts_str}")
            except (ValueError, TypeError):
                # Se não conseguir ler a data, mantém a mensagem
                valid_messages.append(entry)

        # 2. Limitar quantidade máxima (mantém as mais recentes)
        if len(valid_messages) > self.MAX_MESSAGES_PER_USER:
            valid_messages = valid_messages[-self.MAX_MESSAGES_PER_USER:]

        # Atualizar
        removed = original_count - len(valid_messages)
        if removed > 0:
            self.logger.info(f"{self._logger_prefix} Limpeza para {user_id}: {removed} mensagens arquivadas")
            self._conversations[user_id] = valid_messages

        return removed

    async def initialize(self) -> None:
        self.logger.info(f"{self._logger_prefix} Inicializando...")
        await self._load_memories()
        
        # Aplicar limpeza inicial em todos os usuários
        total_removed = 0
        for user_id in list(self._conversations.keys()):
            total_removed += self._cleanup_old_memories(user_id)
        if total_removed > 0:
            self.logger.info(f"{self._logger_prefix} Limpeza inicial concluída: {total_removed} mensagens arquivadas")
            await self._save_memories()
        
        self._running = True
        self.logger.info(f"{self._logger_prefix} Inicializado")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recupera histórico, preferências e mensagens relevantes.

        O registro da mensagem é responsabilidade de _persist_turn() no Brain,
        para evitar que a mesma entrada seja gravada duas vezes.
        """
        if not isinstance(context, dict):
            context = {}
        user_id = str(context.get("user_id") or context.get("user") or "unknown")
        message = str(context.get("message") or "")
        
        # Aplica limpeza antes de carregar o contexto
        self._cleanup_old_memories(user_id)
        
        history = self._get_user_history(user_id, limit=self.RECENT_CONTEXT_LIMIT)
        preferences = self._get_user_preferences(user_id)
        relevant = self._search_relevant_memories(user_id, message)
        total_count = len(self._conversations.get(user_id, []))
        memory_data = {
            "user_id": user_id,
            "history": history,
            "preferences": preferences,
            "relevant_memories": relevant,
            "history_count": total_count,
            "timestamp": datetime.now().isoformat(),
        }
        self.logger.info(f"{self._logger_prefix} {len(history)} no contexto, {total_count} total")
        try:
            await self.event_bus.publish_async(
                EventType.MEMORY_RETRIEVED,
                {"context": context, "memory": memory_data, "timestamp": datetime.now().isoformat()},
                source="memory_manager",
            )
        except Exception as exc:
            self.logger.warning(f"{self._logger_prefix} Falha ao publicar MEMORY_RETRIEVED: {exc}")
        return memory_data

    def _get_user_history(self, user_id: str, limit: int = None) -> List[Dict]:
        # Recupera somente declaracoes humanas para contexto factual.
        # O historico completo continua preservado no armazenamento.
        if limit is None:
            limit = self.RECENT_CONTEXT_LIMIT
        history = self._conversations.get(str(user_id), [])
        if limit <= 0:
            return []
        humanas = [
            entry for entry in history
            if isinstance(entry, dict)
            and entry.get("role") == "user"
        ]
        return [dict(entry) for entry in humanas[-limit:]]

    def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        return dict(self._preferences.get(str(user_id), {}))

    def _search_relevant_memories(self, user_id: str, message: str) -> List[Dict]:
        history = self._conversations.get(str(user_id), [])
        if not history or not isinstance(message, str):
            return []

        keywords = {
            word.casefold()
            for word in re.findall(r"\w+", message, re.UNICODE)
            if len(word) > 3
        }
        if not keywords:
            return []

        scored = []
        for index, entry in enumerate(history):
            if not isinstance(entry, dict):
                continue

            # Respostas da IA nao sao fontes de fatos pessoais.
            if entry.get("role") != "user":
                continue

            content = str(entry.get("content", ""))
            words = set(re.findall(r"\w+", content.casefold(), re.UNICODE))
            score = len(keywords & words)

            if score:
                scored.append((score, index, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [dict(item[2]) for item in scored[:5]]

    def _add_to_history(self, user_id: str, message: str, role: str = "user") -> None:
        user_id = str(user_id)
        message = str(message)
        if not message.strip():
            return
        history = self._conversations.setdefault(user_id, [])
        # Evita repetição consecutiva da mesma entrada
        if history and history[-1].get("role") == role and history[-1].get("content") == message:
            return
        history.append({"role": role, "content": message, "timestamp": datetime.now().isoformat()})
        
        # Aplica limpeza após adicionar nova mensagem
        self._cleanup_old_memories(user_id)

    async def store_response(self, user_id: str, response: str) -> None:
        """Armazena a resposta da assistente no histórico e salva imediatamente."""
        self._add_to_history(user_id, response, role="assistant")
        await self._save_memories()

    @staticmethod
    def _validate_conversations(data: Any) -> Dict[str, List[Dict[str, Any]]]:
        if not isinstance(data, dict):
            return {}
        validated = {}
        for user_id, entries in data.items():
            if not isinstance(entries, list):
                validated[str(user_id)] = []
                continue
            valid_entries = [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("content"), str)]
            validated[str(user_id)] = valid_entries
        return validated

    async def _load_memories(self) -> None:
        if self._memory_path.exists():
            try:
                with self._memory_path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                    self._conversations = self._validate_conversations(loaded)
                    total = sum(len(h) for h in self._conversations.values())
                    self.logger.info(f"{self._logger_prefix} Carregadas {total} mensagens em {len(self._conversations)} usuários")
            except (OSError, ValueError, TypeError) as exc:
                self.logger.error(f"{self._logger_prefix} Falha ao carregar conversas; arquivo preservado: {exc}")
        if self._preferences_path.exists():
            try:
                with self._preferences_path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                    if not isinstance(loaded, dict):
                        raise ValueError("preferences.json deve conter um objeto JSON")
                    self._preferences = {str(k): v for k, v in loaded.items() if isinstance(v, dict)}
            except (OSError, ValueError, TypeError) as exc:
                self.logger.error(f"{self._logger_prefix} Falha ao carregar preferências; arquivo preservado: {exc}")

    @staticmethod
    def _write_json_atomic(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                            prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    async def _save_memories(self) -> None:
        async with self._save_lock:
            try:
                # Cria backup antes de sobrescrever cada arquivo
                self._make_backup(self._memory_path)
                self._make_backup(self._preferences_path)
                
                self._write_json_atomic(self._memory_path, self._conversations)
                self._write_json_atomic(self._preferences_path, self._preferences)
            except (OSError, TypeError, ValueError) as exc:
                self.logger.error(f"{self._logger_prefix} Erro ao salvar memórias: {exc}")
                raise

    async def shutdown(self) -> None:
        self.logger.info(f"{self._logger_prefix} Desligando...")
        await self._save_memories()
        self._running = False
        self.logger.info(f"{self._logger_prefix} Desligado")

    async def health_check(self) -> dict:
        total_msgs = sum(len(history) for history in self._conversations.values())
        return {
            "status": "running" if self._running else "stopped",
            "users": len(self._conversations),
            "total_messages": total_msgs,
            "backup_enabled": True,
            "retention_limit": self.MAX_MESSAGES_PER_USER,
            "retention_days": self.MAX_CONVERSATION_AGE_DAYS,
        }
