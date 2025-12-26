from __future__ import annotations

from typing import Tuple

from utils.firebase_utils import init_firestore


def _is_active(status: object) -> bool:
    if status is None:
        return True
    if isinstance(status, bool):
        return status
    return str(status).strip().lower() in {"active", "ativo", "ativa", "enabled", "true", "1"}


def autenticar_usuario(email: str | None, senha: str | None) -> Tuple[bool, str | None, str | None]:
    if not email or not senha:
        return False, None, None

    email_normalizado = email.strip().lower()
    db = init_firestore()
    doc_ref = db.collection("users").document(email_normalizado).get()
    data = doc_ref.to_dict() if doc_ref.exists else None

    if not data:
        query = db.collection("users").where("email", "==", email_normalizado).limit(1).get()
        if query:
            data = query[0].to_dict()
        else:
            return False, None, None

    senha_db = data.get("senha")
    if senha_db is None or senha_db != senha:
        return False, None, None

    if not _is_active(data.get("status")):
        return False, None, None

    nome = data.get("nome") or data.get("name") or data.get("usuario")
    return True, data.get("role"), nome
