from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Tuple

from utils.firebase_utils import init_firestore

_FIRESTORE_TIMEOUT_S = 6


def _is_active(status: object) -> bool:
    if status is None:
        return True
    if isinstance(status, bool):
        return status
    return str(status).strip().lower() in {"active", "ativo", "ativa", "enabled", "true", "1"}


def autenticar_usuario(email: str | None, senha: str | None) -> Tuple[bool, str | None]:
    if not email or not senha:
        return False, None

    email_normalizado = email.strip().lower()
    db = init_firestore()

    def _buscar_usuario():
        doc_ref = db.collection("users").document(email_normalizado).get()
        if doc_ref.exists:
            return doc_ref.to_dict() or {}
        query = db.collection("users").where("email", "==", email_normalizado).limit(1).get()
        if query:
            return query[0].to_dict() or {}
        return None

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_buscar_usuario)
            data = future.result(timeout=_FIRESTORE_TIMEOUT_S)
    except TimeoutError:
        return False, None
    except Exception:
        return False, None

    senha_db = data.get("senha")
    if senha_db is None or senha_db != senha:
        return False, None

    if not _is_active(data.get("status")):
        return False, None

    return True, data.get("role")
