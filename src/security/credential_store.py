"""Armazenamento experimental de verificadores de credenciais."""

import json
import os
import tempfile
from pathlib import Path


class CredentialStore:
    """Persistencia atomica de registros de credenciais."""

    VERSION = 1

    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def _validate_record(record):
        if not isinstance(record, dict):
            raise ValueError("Registro invalido")

        if set(record) != {"salt", "hash"}:
            raise ValueError("Campos de credencial invalidos")

        for field, expected_bytes in (("salt", 16), ("hash", 32)):
            value = record[field]

            if not isinstance(value, str):
                raise ValueError("Formato de credencial invalido")

            if len(value) != expected_bytes * 2:
                raise ValueError("Tamanho de credencial invalido")

            try:
                bytes.fromhex(value)
            except ValueError as error:
                raise ValueError("Hexadecimal invalido") from error

    def load(self):
        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)

        if not isinstance(payload, dict):
            raise ValueError("Arquivo de credenciais invalido")

        if payload.get("version") != self.VERSION:
            raise ValueError("Versao de credenciais incompat?vel")

        records = payload.get("credentials")

        if not isinstance(records, dict):
            raise ValueError("Colecao de credenciais invalida")

        for user_id, record in records.items():
            if (
                not isinstance(user_id, str)
                or not user_id
                or user_id != user_id.strip().casefold()
            ):
                raise ValueError("Identificador invalido")

            self._validate_record(record)

        return records

    def save(self, records):
        if not isinstance(records, dict):
            raise ValueError("Colecao invalida")

        for user_id, record in records.items():
            if (
                not isinstance(user_id, str)
                or not user_id
                or user_id != user_id.strip().casefold()
            ):
                raise ValueError("Identificador invalido")

            self._validate_record(record)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        if self.path.exists():
            raise FileExistsError(
                "Arquivo existente: substituicao nao autorizada"
            )

        payload = {
            "version": self.VERSION,
            "credentials": records,
        }

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".credentials_",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())

            # Publicacao sem sobrescrever destino existente.
            os.link(temp_path, self.path)

        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
