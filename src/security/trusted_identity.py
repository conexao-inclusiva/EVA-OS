"""Resolucao experimental de identidade autenticada da EVA-OS."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustedIdentity:
    user_id: str | None
    role: str
    authenticated: bool


class TrustedIdentityResolver:
    """Nao confia em papeis declarados pelo usuario."""

    def __init__(self, auth, administrators=()):
        self.auth = auth
        self._administrators = frozenset(
            str(user).strip().casefold()
            for user in administrators
            if str(user).strip()
        )

    def resolve(self, token):
        user_id = self.auth.resolve_session(token)

        if not user_id:
            return TrustedIdentity(
                user_id=None,
                role="guest",
                authenticated=False,
            )

        role = (
            "admin"
            if user_id in self._administrators
            else "user"
        )

        return TrustedIdentity(
            user_id=user_id,
            role=role,
            authenticated=True,
        )

    def sanitize_context(self, context, token=None):
        """Produz novo contexto sem aceitar identidade declarada."""
        if not isinstance(context, dict):
            context = {}

        identity = self.resolve(token)

        # Campos de identidade recebidos nao sao confiaveis.
        # Nenhum token e inserido no contexto retornado.
        sanitized = {
            key: value
            for key, value in context.items()
            if key not in (
                "user",
                "user_id",
                "role",
                "auth_token",
                "token",
            )
        }

        sanitized["user"] = {
            "user_id": identity.user_id,
            "role": identity.role,
        }

        if identity.user_id is not None:
            sanitized["user_id"] = identity.user_id

        return sanitized
