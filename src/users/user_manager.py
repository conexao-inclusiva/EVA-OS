# -*- coding: utf-8 -*-

"""
User Manager - Gerencia perfis e preferências dos usuários.
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

# 🔥 CORRIGIDO: Import absoluto (em vez de relativo)
from src.utils.logger import Logger


@dataclass
class UserProfile:
    user_id: str
    name: str = "Usuário"
    preferred_name: Optional[str] = None
    preferred_tone: str = "neutro"
    preferred_response_length: str = "medio"
    preferences: Dict[str, Any] = field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    interaction_count: int = 0
    facts: List[Dict[str, str]] = field(default_factory=list)


class UserManager:
    def __init__(self, event_bus, logger, config):
        self.event_bus = event_bus
        self.logger = Logger.get_logger() if logger is None else logger
        self.config = config or {}
        self._users: Dict[str, UserProfile] = {}
        self._current_user_id: Optional[str] = None
        self.persist_file = config.get("users_persist_file", "data/users.json") if config else "data/users.json"
        self._load_users()
        self.logger.info("👤 [UserManager] Inicializado")
        self.logger.info(f"   {len(self._users)} usuários carregados")
    
    async def initialize(self) -> None:
        self.logger.info("👤 [UserManager] Pronto")
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id", "unknown")
        user_message = context.get("message", "")
        user = self.get_or_create_user(user_id)
        self._current_user_id = user_id
        user.last_seen = datetime.now().isoformat()
        user.interaction_count += 1
        self._save_users()
        return {
            "user_id": user.user_id,
            "name": user.preferred_name or user.name,
            "preferred_tone": user.preferred_tone,
            "preferred_response_length": user.preferred_response_length,
            "interaction_count": user.interaction_count,
            "preferences": user.preferences,
            "facts": user.facts
        }
    
    def get_or_create_user(self, user_id: str, name: str = None) -> UserProfile:
        if user_id in self._users:
            return self._users[user_id]
        user = UserProfile(
            user_id=user_id,
            name=name or "Usuário",
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            interaction_count=0
        )
        self._users[user_id] = user
        self.logger.info(f"👤 [UserManager] Novo usuário criado: {user_id}")
        return user
    
    def get_current_user(self) -> Optional[UserProfile]:
        if self._current_user_id and self._current_user_id in self._users:
            return self._users[self._current_user_id]
        return None
    
    def update_user_preference(self, user_id: str, key: str, value: Any) -> None:
        user = self.get_or_create_user(user_id)
        user.preferences[key] = value
        self._save_users()
    
    def add_fact_about_user(self, user_id: str, fact: str, confidence: float = 0.7) -> None:
        user = self.get_or_create_user(user_id)
        existing = [f for f in user.facts if f["fact"].lower() == fact.lower()]
        if existing:
            return
        user.facts.append({
            "fact": fact,
            "confidence": confidence,
            "learned_at": datetime.now().isoformat()
        })
        self._save_users()
        self.logger.info(f"👤 [UserManager] Fato aprendido sobre {user_id}: {fact}")
    
    def get_user_facts(self, user_id: str) -> List[str]:
        user = self.get_or_create_user(user_id)
        return [f["fact"] for f in user.facts]
    
    def get_user_profile_prompt(self, user_id: str) -> str:
        user = self.get_or_create_user(user_id)
        parts = []
        if user.preferred_name:
            parts.append(f"O usuário prefere ser chamado de {user.preferred_name}.")
        if user.preferred_tone != "neutro":
            parts.append(f"O usuário prefere um tom {user.preferred_tone}.")
        if user.preferred_response_length != "medio":
            parts.append(f"O usuário prefere respostas {user.preferred_response_length}.")
        if user.facts:
            facts_str = ", ".join([f["fact"] for f in user.facts[-5:]])
            parts.append(f"Fatos conhecidos sobre o usuário: {facts_str}.")
        return " ".join(parts) if parts else "Usuário desconhecido. Trate com respeito e educação."
    
    def _load_users(self) -> None:
        try:
            if os.path.exists(self.persist_file):
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, user_data in data.items():
                        profile = UserProfile(
                            user_id=user_id,
                            name=user_data.get("name", "Usuário"),
                            preferred_name=user_data.get("preferred_name"),
                            preferred_tone=user_data.get("preferred_tone", "neutro"),
                            preferred_response_length=user_data.get("preferred_response_length", "medio"),
                            preferences=user_data.get("preferences", {}),
                            first_seen=user_data.get("first_seen"),
                            last_seen=user_data.get("last_seen"),
                            interaction_count=user_data.get("interaction_count", 0),
                            facts=user_data.get("facts", [])
                        )
                        self._users[user_id] = profile
        except Exception as e:
            self.logger.warning(f"⚠️ Erro ao carregar usuários: {e}")
    
    def _save_users(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.persist_file), exist_ok=True)
            data = {}
            for user_id, profile in self._users.items():
                data[user_id] = {
                    "name": profile.name,
                    "preferred_name": profile.preferred_name,
                    "preferred_tone": profile.preferred_tone,
                    "preferred_response_length": profile.preferred_response_length,
                    "preferences": profile.preferences,
                    "first_seen": profile.first_seen,
                    "last_seen": profile.last_seen,
                    "interaction_count": profile.interaction_count,
                    "facts": profile.facts
                }
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"⚠️ Erro ao salvar usuários: {e}")
    
    async def shutdown(self) -> None:
        self._save_users()
        self.logger.info("👤 [UserManager] Desligado")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "total_users": len(self._users),
            "current_user": self._current_user_id,
            "active": self._current_user_id is not None
        }