import re
import unicodedata
from datetime import datetime
from typing import Dict


def _norm_basic(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _title_if_text(s: str) -> str:
    s = _norm_basic(s)
    if not s:
        return s
    preps = {"da", "de", "do", "das", "dos", "e"}
    parts = s.lower().split()
    titled = [p.capitalize() if p not in preps else p for p in parts]
    return " ".join(titled)


def slugify_equipe_nome(name: str) -> str:
    s = _norm_basic(name)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s.lower()


def _status_equipes_normalizado(status: str) -> str:
    s = _norm_basic(status).lower()
    if s == "ativa":
        return "Ativa"
    if s == "inativa":
        return "Inativa"
    # default
    return "Inativa"


def formatar_equipe_para_firestore(dados: Dict[str, object]) -> Dict[str, object]:
    """Formata e normaliza o payload de equipe para persistência no Firestore."""
    nome            = _title_if_text(dados.get("NOME", ""))
    orientador      = _title_if_text(dados.get("ORIENTADOR", ""))
    descricao       = _norm_basic(dados.get("DESCRICAO", dados.get("DESCRIÇÃO", "")))
    status          = _status_equipes_normalizado(dados.get("STATUS", ""))

    out = {
        "NOME": nome,
        "ORIENTADOR": orientador,
        "DESCRICAO": descricao,
        "STATUS": status,
        "DATA CADASTRO": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return out
