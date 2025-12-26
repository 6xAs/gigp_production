from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


CSV_PATRIMONIOS = (
    Path(__file__).resolve().parent.parent / "data" / "patrimonio_gp" / "gerenciamento_patrimonial_producao.csv"
)

COLUNAS_TEXTUAIS: Iterable[str] = (
    "ITEM",
    "CATEGORIA",
    "MARCA",
    "MODELO",
    "ESTADO",
    "SITUACAO_USO",
    "VIDA_UTIL",
    "OBSERVACOES",
    "LOCAL_OBJETO",
)

COLUNAS_NUMERICAS: Iterable[str] = ("QUANTIDADE", "PRECO_ESTIMADO")

COLUNAS_BASE = [
    "CODIGO",
    "ITEM",
    "CATEGORIA",
    "MARCA",
    "MODELO",
    "QUANTIDADE",
    "PRECO_ESTIMADO",
    "ESTADO",
    "SITUACAO_USO",
    "VIDA_UTIL",
    "LOCAL_OBJETO",
    "DATA_ATUALIZACAO",
    "OBSERVACOES",
]


def preparar_patrimonios_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    for coluna in COLUNAS_TEXTUAIS:
        if coluna in df.columns:
            df[coluna] = df[coluna].fillna("").astype(str).str.strip()
        else:
            df[coluna] = ""

    for coluna in COLUNAS_NUMERICAS:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce").fillna(0)
        else:
            df[coluna] = 0.0

    if "DATA_ATUALIZACAO" in df.columns:
        df["DATA_ATUALIZACAO"] = pd.to_datetime(df["DATA_ATUALIZACAO"], errors="coerce")
    else:
        df["DATA_ATUALIZACAO"] = pd.NaT
    df["ANO_ATUALIZACAO"] = df["DATA_ATUALIZACAO"].dt.year
    df["MES_ATUALIZACAO"] = df["DATA_ATUALIZACAO"].dt.month
    df["DATA_ATUALIZACAO_BR"] = df["DATA_ATUALIZACAO"].dt.strftime("%d/%m/%Y").fillna("")

    df["VALOR_TOTAL"] = df.get("QUANTIDADE", 0) * df.get("PRECO_ESTIMADO", 0)

    if "OBSERVACOES" not in df.columns:
        df["OBSERVACOES"] = ""
    if "LOCAL_OBJETO" not in df.columns:
        df["LOCAL_OBJETO"] = ""

    return df


def carregar_patrimonios_csv() -> pd.DataFrame:
    if not CSV_PATRIMONIOS.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(CSV_PATRIMONIOS)
    except Exception:
        return pd.DataFrame()
    return preparar_patrimonios_dataframe(df)


def salvar_patrimonio_csv(dados: dict) -> dict:
    if CSV_PATRIMONIOS.exists():
        try:
            df_raw = pd.read_csv(CSV_PATRIMONIOS)
        except Exception:
            df_raw = pd.DataFrame(columns=COLUNAS_BASE)
    else:
        df_raw = pd.DataFrame(columns=COLUNAS_BASE)

    for coluna in COLUNAS_BASE:
        if coluna not in df_raw.columns:
            df_raw[coluna] = ""

    novo_codigo = _gerar_codigo(df_raw, dados.get("CODIGO"))
    registro = _normalizar_registro(dados, novo_codigo)

    df_raw = pd.concat([df_raw, pd.DataFrame([registro])], ignore_index=True)
    df_raw = df_raw[COLUNAS_BASE]
    df_raw.to_csv(CSV_PATRIMONIOS, index=False)
    return registro


def salvar_ou_atualizar_patrimonio_csv(dados: dict) -> dict:
    if CSV_PATRIMONIOS.exists():
        try:
            df_raw = pd.read_csv(CSV_PATRIMONIOS)
        except Exception:
            df_raw = pd.DataFrame(columns=COLUNAS_BASE)
    else:
        df_raw = pd.DataFrame(columns=COLUNAS_BASE)

    for coluna in COLUNAS_BASE:
        if coluna not in df_raw.columns:
            df_raw[coluna] = ""

    codigo_informado = dados.get("CODIGO")
    registro = _padronizar_campos(dados)
    try:
        registro["CODIGO"] = int(float(codigo_informado))
    except Exception:
        if codigo_informado:
            registro["CODIGO"] = codigo_informado
        else:
            registro["CODIGO"] = _gerar_codigo(df_raw, codigo_informado)

    mask = df_raw["CODIGO"].astype(str) == str(registro["CODIGO"])
    if mask.any():
        df_raw.loc[mask, COLUNAS_BASE] = pd.DataFrame([registro])[COLUNAS_BASE].values
    else:
        df_raw = pd.concat([df_raw, pd.DataFrame([registro])], ignore_index=True)

    df_raw = df_raw[COLUNAS_BASE]
    df_raw.to_csv(CSV_PATRIMONIOS, index=False)
    return registro


def remover_patrimonios_csv(codigos: list) -> int:
    if not codigos:
        return 0
    if CSV_PATRIMONIOS.exists():
        try:
            df_raw = pd.read_csv(CSV_PATRIMONIOS)
        except Exception:
            return 0
    else:
        return 0

    codigos_set = {str(c) for c in codigos}
    antes = len(df_raw)
    df_raw = df_raw[~df_raw["CODIGO"].astype(str).isin(codigos_set)]
    removidos = max(0, antes - len(df_raw))
    df_raw.to_csv(CSV_PATRIMONIOS, index=False)
    return removidos


def _gerar_codigo(df_raw: pd.DataFrame, codigo_informado) -> int:
    if codigo_informado:
        try:
            return int(codigo_informado)
        except Exception:
            pass
    if df_raw.empty or "CODIGO" not in df_raw.columns:
        return 1
    try:
        return int(pd.to_numeric(df_raw["CODIGO"], errors="coerce").max()) + 1
    except Exception:
        return len(df_raw) + 1


def _normalizar_registro(dados: dict, codigo: int) -> dict:
    registro = _padronizar_campos(dados)
    registro["CODIGO"] = codigo
    return registro


def _padronizar_campos(dados: dict) -> dict:
    registro = {col: "" for col in COLUNAS_BASE}
    registro["ITEM"] = _texto(dados.get("ITEM"))
    registro["CATEGORIA"] = _texto(dados.get("CATEGORIA")) or "Indefinido"
    registro["MARCA"] = _texto(dados.get("MARCA")) or "Indefinido"
    registro["MODELO"] = _texto(dados.get("MODELO")) or "Indefinido"
    registro["ESTADO"] = padronizar_estado_label(_texto(dados.get("ESTADO")) or "Em bom estado")
    registro["SITUACAO_USO"] = _texto(dados.get("SITUACAO_USO")) or "Em uso"
    registro["VIDA_UTIL"] = _texto(dados.get("VIDA_UTIL")) or "Indeterminado"
    registro["OBSERVACOES"] = _texto(dados.get("OBSERVACOES"))
    registro["LOCAL_OBJETO"] = _texto(dados.get("LOCAL_OBJETO"))

    registro["QUANTIDADE"] = _numero_inteiro(dados.get("QUANTIDADE"))
    registro["PRECO_ESTIMADO"] = _numero_decimal(dados.get("PRECO_ESTIMADO"))
    registro["DATA_ATUALIZACAO"] = _resolver_data(dados.get("DATA_ATUALIZACAO"))
    return registro


def _texto(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    return texto


def _numero_inteiro(valor) -> int:
    try:
        return int(float(valor))
    except Exception:
        return 0


def _numero_decimal(valor) -> float:
    try:
        return round(float(valor), 2)
    except Exception:
        return 0.0


def _resolver_data(valor) -> str:
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%d")
    if valor:
        return str(valor).split("T")[0][:10]
    return datetime.now().strftime("%Y-%m-%d")


def padronizar_estado_label(valor: str) -> str:
    texto = _texto(valor)
    if not texto:
        return ""
    texto_limpo = " ".join(texto.split())
    chave = texto_limpo.replace(",", "").casefold()
    if chave in {"usado", "desgastado mas funcional"}:
        return "Desgastado, mas funcional"
    return texto_limpo


def formatar_patrimonio_para_firestore(dados: dict) -> dict:
    registro = _padronizar_campos(dados)
    codigo = dados.get("CODIGO")
    try:
        registro["CODIGO"] = int(float(codigo))
    except Exception:
        registro["CODIGO"] = codigo or ""
    registro["VALOR_TOTAL"] = registro["QUANTIDADE"] * registro["PRECO_ESTIMADO"]
    return registro
