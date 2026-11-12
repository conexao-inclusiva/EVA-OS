"""Autenticacao hibrida isolada da EVA-OS.

Este modulo nao autentica automaticamente usuarios existentes.
As credenciais devem ser cadastradas por um fluxo confiavel.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthSession:
    user_id: str
    token: str
    expires_at: float


class HybridAuth:
    """Credenciais individuais e sessoes temporarias em memoria."""

    def __init__(
        self,
        session_seconds=900,
        max_attempts=5,
        lock_seconds=300,
    ):
        self.session_seconds = session_seconds
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self._credentials = {}
        self._sessions = {}
        self._failures = {}
        self._locked_until = {}

    @staticmethod
    def _derive(secret, salt):
        return hashlib.pbkdf2_hmac(
            "sha256",
            secret.encode("utf-8"),
            salt,
            600000,
        )

    def enroll(self, user_id, secret):
        """Cadastro explicito; nao deve ser exposto a usuarios anonimos."""
        user_id = str(user_id).strip().casefold()

        if not user_id:
            raise ValueError("Identificador invalido")

        if not isinstance(secret, str) or len(secret) < 6:
            raise ValueError("Credencial deve ter pelo menos 6 caracteres")

        if user_id in self._credentials:
            raise ValueError("Credencial ja cadastrada")

        salt = secrets.token_bytes(16)
        digest = self._derive(secret, salt)
        self._credentials[user_id] = (salt, digest)

    def authenticate(self, user_id, secret):
        """Retorna token temporario ou None."""
        user_id = str(user_id).strip().casefold()
        now = time.monotonic()

        if now < self._locked_until.get(user_id, 0):
            return None

        stored = self._credentials.get(user_id)

        if stored is None or not isinstance(secret, str):
            return None

        salt, expected = stored
        actual = self._derive(secret, salt)

        if not hmac.compare_digest(actual, expected):
            failures = self._failures.get(user_id, 0) + 1
            self._failures[user_id] = failures

            if failures >= self.max_attempts:
                self._locked_until[user_id] = now + self.lock_seconds
                self._failures[user_id] = 0

            return None

        self._failures.pop(user_id, None)

        token = secrets.token_urlsafe(32)
        self._sessions[token] = AuthSession(
            user_id=user_id,
            token=token,
            expires_at=now + self.session_seconds,
        )
        return token

    def resolve_session(self, token):
        """Retorna usuario autenticado se a sessao estiver valida."""
        if not isinstance(token, str) or not token:
            return None

        session = self._sessions.get(token)

        if session is None:
            return None

        if time.monotonic() >= session.expires_at:
            self._sessions.pop(token, None)
            return None

        return session.user_id

    def logout(self, token):
        """Revoga uma sessao."""
        return self._sessions.pop(token, None) is not None

    def can_access_private(self, token, user_id):
        """Permite acesso somente ao proprio perfil autenticado."""
        authenticated = self.resolve_session(token)
        requested = str(user_id).strip().casefold()

        return (
            authenticated is not None
            and authenticated == requested
        )
