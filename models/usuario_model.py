from __future__ import annotations

from typing import Iterable


USUARIOS_AUTORIZADOS: list[dict[str, str]] = [
    {"usuario": "gestor.gp", "senha": "gp#2026"},
    {"usuario": "anderson.seixas", "senha": "em*c2admin"},
    {"usuario": "equipe.vingadores", "senha": "vingadores@2025*"},
]


def listar_usuarios() -> Iterable[dict[str, str]]:
    """Retorna o vetor de usuários autorizados para consulta externa."""
    return tuple(USUARIOS_AUTORIZADOS)


def autenticar_usuario(usuario: str | None, senha: str | None) -> bool:
    """Valida se as credenciais informadas existem na lista estática do projeto."""
    if not usuario or not senha:
        return False
    usuario_normalizado = usuario.strip().lower()
    return any(
        usuario_normalizado == item["usuario"].strip().lower() and senha == item["senha"]
        for item in USUARIOS_AUTORIZADOS
    )
