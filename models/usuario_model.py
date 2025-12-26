from __future__ import annotations

from typing import Tuple

from utils.firebase_utils import init_firestore


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
    doc_ref = db.collection("users").document(email_normalizado).get()
    if not doc_ref.exists:
        return False, None
    data = doc_ref.to_dict() or {}

    senha_db = data.get("senha")
    if senha_db is None or senha_db != senha:
        return False, None

    if not _is_active(data.get("status")):
        return False, None

    return True, data.get("role")
