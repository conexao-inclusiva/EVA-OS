"""Integracao experimental de autenticacao com credenciais persistentes."""

from src.security.credential_store import CredentialStore
from src.security.hybrid_auth import HybridAuth


class PersistentAuth:
    """Autenticacao com verificadores persistentes e sessoes em memoria."""

    def __init__(self, credential_path, **auth_options):
        self.store = CredentialStore(credential_path)
        self.auth = HybridAuth(**auth_options)
        self._load_credentials()

    def _load_credentials(self):
        records = self.store.load()

        for user_id, record in records.items():
            self.auth._credentials[user_id] = (
                bytes.fromhex(record["salt"]),
                bytes.fromhex(record["hash"]),
            )

    def enroll_initial(self, user_id, secret):
        """Cadastro inicial somente quando o armazenamento nao existe.

        O chamador deve garantir autorizacao administrativa fora deste modulo.
        """
        if self.store.path.exists():
            raise PermissionError(
                "Cadastro inicial indisponivel: armazenamento existente"
            )

        if self.auth._credentials:
            raise PermissionError("Credenciais ja carregadas")

        self.auth.enroll(user_id, secret)

        records = {}

        for identity, (salt, digest) in self.auth._credentials.items():
            records[identity] = {
                "salt": salt.hex(),
                "hash": digest.hex(),
            }

        try:
            self.store.save(records)
        except Exception:
            self.auth._credentials.clear()
            raise

    def authenticate(self, user_id, secret):
        return self.auth.authenticate(user_id, secret)

    def resolve_session(self, token):
        return self.auth.resolve_session(token)

    def can_access_private(self, token, user_id):
        return self.auth.can_access_private(token, user_id)

    def logout(self, token):
        return self.auth.logout(token)
