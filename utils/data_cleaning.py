import re
import unicodedata
import pandas as pd
from typing import Dict, Iterable


def _norm_basic(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_ascii_lower(s: str) -> str:
    s = _norm_basic(s)
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
    return s.lower()


def _title_if_text(s: str) -> str:
    s = _norm_basic(s)
    if not s:
        return s
    # Mantém preposições minúsculas
    preps = {"da", "de", "do", "das", "dos", "e"}
    parts = s.lower().split()
    titled = [p.capitalize() if p not in preps else p for p in parts]
    return " ".join(titled)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def _similar(a: str, b: str) -> float:
    a2, b2 = _norm_ascii_lower(a), _norm_ascii_lower(b)
    if not a2 and not b2:
        return 1.0
    dist = _levenshtein(a2, b2)
    max_len = max(len(a2), len(b2)) or 1
    return 1 - (dist / max_len)


def build_canonical_map(values: Iterable[str], threshold: float = 0.86) -> Dict[str, str]:
    # Escolhe a variante mais frequente como canônica por cluster
    vals = [v for v in values if isinstance(v, str) and _norm_basic(v)]
    if not vals:
        return {}
    freq = pd.Series(vals).value_counts().to_dict()
    unique = list(freq.keys())
    canonical_for = {}
    used = set()
    # Ordena por frequência desc
    unique_sorted = sorted(unique, key=lambda x: (-freq[x], x))
    for base in unique_sorted:
        if base in used:
            continue
        canonical_for[base] = base
        used.add(base)
        for other in unique_sorted:
            if other in used:
                continue
            if _similar(base, other) >= threshold:
                canonical_for[other] = base
                used.add(other)
    # Para valores nunca vistos (vazios), mapeia para si
    return canonical_for


def clean_members_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()

    if "PROJETO ATUAL" not in df.columns:
        df["PROJETO ATUAL"] = ""

    # Trim e normalização básica
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(_norm_basic)

    # Emails em minúsculo
    if "EMAIL" in df.columns:
        df["EMAIL"] = df["EMAIL"].str.lower()

    # Nomes e campos de texto em Title case
    for col in ["NOME", "ORIENTADOR", "CURSO", "EQUIPE DE PROJETO", "PROJETO ATUAL"]:
        if col in df.columns:
            df[col] = df[col].apply(_title_if_text)

    # Normaliza STATUS
    if "STATUS" in df.columns:
        mapa_status = {
            "ativo": "Ativo",
            "inativo": "Inativo",
            "pendente": "Pendente",
        }
        df["STATUS"] = df["STATUS"].apply(lambda s: mapa_status.get(_norm_ascii_lower(s), "Pendente"))

    # Normaliza TIPO MEMBRO
    if "TIPO MEMBRO" in df.columns:
        mapa_tipo = {
            "discente": "Discente",
            "aluno": "Discente",
            "estudante": "Discente",
            "professor": "Professor",
            "docente": "Professor",
        }
        df["TIPO MEMBRO"] = df["TIPO MEMBRO"].apply(lambda s: mapa_tipo.get(_norm_ascii_lower(s), _title_if_text(s)))

    # Corrige ANO (ex.: 2024.0 -> 2024)
    if "ANO" in df.columns:
        def fix_ano(v):
            if pd.isna(v) or v == "":
                return ""
            try:
                # tenta converter float/string para int
                i = int(float(str(v).replace(",", ".")))
                return str(i)
            except Exception:
                return _norm_basic(str(v))
        df["ANO"] = df["ANO"].apply(fix_ano)

    # Clusteriza e padroniza nomes de ORIENTADOR semelhantes
    if "ORIENTADOR" in df.columns:
        can_map = build_canonical_map(df["ORIENTADOR"].dropna().unique().tolist())
        df["ORIENTADOR"] = df["ORIENTADOR"].apply(lambda s: can_map.get(s, _title_if_text(s)))

    # Remove duplicados por CPF (ou EMAIL como fallback)
    if "CPF" in df.columns:
        df = df.sort_values(by=["CPF"]).drop_duplicates(subset=["CPF"], keep="first")
    elif "EMAIL" in df.columns:
        df = df.sort_values(by=["EMAIL"]).drop_duplicates(subset=["EMAIL"], keep="first")

    return df.reset_index(drop=True)


def save_clean_csv(df: pd.DataFrame, path: str) -> None:
    if df is None:
        return
    df.to_csv(path, index=False)

