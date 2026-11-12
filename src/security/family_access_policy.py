"""Politica experimental de autorizacao familiar da EVA-OS."""

from enum import Enum


class FamilyResource(str, Enum):
    PUBLIC = "public"
    PERSONAL_MEMORY = "personal_memory"
    PRIVATE_HISTORY = "private_history"
    FAMILY_TREE = "family_tree"
    FAMILY_EDIT = "family_edit"
    ADMINISTRATION = "administration"


class FamilyAccessPolicy:
    """Autorizacao explicita com negacao por padrao."""

    def __init__(self, auth):
        self.auth = auth
        self._family_readers = set()
        self._family_editors = set()
        self._administrators = set()

    def configure_roles(
        self,
        *,
        readers=(),
        editors=(),
        administrators=(),
    ):
        """Configuracao interna; nao expor ao chat ou a voz."""
        self._family_readers = {
            str(user).strip().casefold() for user in readers
        }
        self._family_editors = {
            str(user).strip().casefold() for user in editors
        }
        self._administrators = {
            str(user).strip().casefold() for user in administrators
        }

    def authorize(self, token, resource, owner_id=None):
        """Decide acesso conforme sessao e recurso solicitado."""
        try:
            resource = FamilyResource(resource)
        except (ValueError, TypeError):
            return False

        if resource == FamilyResource.PUBLIC:
            return True

        user_id = self.auth.resolve_session(token)

        if user_id is None:
            return False

        if resource in (
            FamilyResource.PERSONAL_MEMORY,
            FamilyResource.PRIVATE_HISTORY,
        ):
            if owner_id is None:
                return False

            return user_id == str(owner_id).strip().casefold()

        if resource == FamilyResource.FAMILY_TREE:
            return (
                user_id in self._family_readers
                or user_id in self._family_editors
                or user_id in self._administrators
            )

        if resource == FamilyResource.FAMILY_EDIT:
            return (
                user_id in self._family_editors
                or user_id in self._administrators
            )

        if resource == FamilyResource.ADMINISTRATION:
            return user_id in self._administrators

        return False
