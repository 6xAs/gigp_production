
from datetime import datetime
from pathlib import Path

import pandas as pd


CSV_MEMBROS = Path(__file__).resolve().parent.parent / "data" / "membros_gp" / "tratados" / "membros_gp_tratados_.csv"


def carregar_membros_csv() -> pd.DataFrame:
    """Retorna membros do CSV local usado como base de sincronização."""
    if not CSV_MEMBROS.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(CSV_MEMBROS)
    except Exception:
        return pd.DataFrame()


def formatar_membro_para_firestore(dados):
    if isinstance(dados.get("DATA NASCIMENTO"), pd.Timestamp):
        dados["DATA NASCIMENTO"] = dados["DATA NASCIMENTO"].strftime("%Y-%m-%d")

    dados["DATA CADASTRO"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return dados
