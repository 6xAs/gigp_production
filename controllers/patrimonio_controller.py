from __future__ import annotations

from uuid import uuid4

import pandas as pd

from models.patrimonio_model import (
    carregar_patrimonios_csv,
    formatar_patrimonio_para_firestore,
    padronizar_estado_label,
    preparar_patrimonios_dataframe,
    remover_patrimonios_csv,
    salvar_ou_atualizar_patrimonio_csv,
    salvar_patrimonio_csv,
)
from utils.firebase_utils import init_firestore

db = init_firestore()
COLLECTION = "patrimonios_gp"


def listar_patrimonios() -> pd.DataFrame:
    try:
        df = listar_patrimonios_firestore()
        if not df.empty:
            return df
    except Exception:
        pass
    df = carregar_patrimonios_csv()
    if df.empty:
        return pd.DataFrame()
    return _normalizar_dataframe(df)


def listar_patrimonios_firestore() -> pd.DataFrame:
    _garantir_dados_firestore()
    documentos = list(db.collection(COLLECTION).stream())
    linhas: list[dict] = []
    atualizacoes: list[tuple[str, str]] = []
    for doc in documentos:
        dados = doc.to_dict() or {}
        if "CODIGO" not in dados or dados["CODIGO"] in ("", None):
            dados["CODIGO"] = doc.id
        estado_padrao = padronizar_estado_label(dados.get("ESTADO", ""))
        if estado_padrao and estado_padrao != dados.get("ESTADO", ""):
            dados["ESTADO"] = estado_padrao
            atualizacoes.append((str(doc.id), estado_padrao))
        linhas.append(dados)
    for doc_id, estado in atualizacoes:
        try:
            db.collection(COLLECTION).document(doc_id).update({"ESTADO": estado})
        except Exception:
            continue
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(linhas)
    return _normalizar_dataframe(df)


def cadastrar_patrimonio(dados: dict) -> dict:
    registro = salvar_patrimonio_csv(dados)
    try:
        salvar_patrimonio_firestore(registro)
    except Exception:
        pass
    return registro


def salvar_patrimonio_firestore(dados: dict) -> dict:
    registro = formatar_patrimonio_para_firestore(dados)
    doc_id = registro.get("CODIGO") or registro.get("ITEM") or str(uuid4())
    db.collection(COLLECTION).document(str(doc_id)).set(registro)
    return registro


def salvar_ou_atualizar_patrimonio(dados: dict) -> dict:
    registro = salvar_ou_atualizar_patrimonio_csv(dados)
    try:
        salvar_patrimonio_firestore(registro)
    except Exception:
        pass
    return registro


def deletar_patrimonios(codigos: list) -> int:
    if not codigos:
        return 0
    removidos_csv = remover_patrimonios_csv(codigos)
    for codigo in codigos:
        try:
            db.collection(COLLECTION).document(str(codigo)).delete()
        except Exception:
            continue
    return removidos_csv


def _garantir_dados_firestore():
    docs = list(db.collection(COLLECTION).limit(1).stream())
    if docs:
        return
    df_csv = carregar_patrimonios_csv()
    if df_csv.empty:
        return
    for _, row in df_csv.iterrows():
        try:
            salvar_patrimonio_firestore(row.to_dict())
        except Exception:
            continue


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = preparar_patrimonios_dataframe(df)
    df["ESTADO"] = df["ESTADO"].apply(padronizar_estado_label)
    df["ESTADO_NORMALIZADO"] = df["ESTADO"].astype(str).str.strip().str.title()
    df["ESTADO_NORMALIZADO"] = df["ESTADO_NORMALIZADO"].replace(
        {"Desgastado, Mas Funcional": "Desgastado, mas funcional"}
    )
    df["SITUACAO_NORMALIZADA"] = df["SITUACAO_USO"].astype(str).str.strip().str.title()
    df["CATEGORIA_NORMALIZADA"] = df["CATEGORIA"].astype(str).str.strip().str.title()
    return df


def calcular_indicadores(df: pd.DataFrame) -> dict[str, float | int]:
    if df.empty:
        return {
            "total_registros": 0,
            "quantidade_total": 0,
            "valor_total": 0.0,
            "valor_em_uso": 0.0,
            "valor_danificado": 0.0,
            "categorias_unicas": 0,
        }
    valor_total = float(df["VALOR_TOTAL"].sum())
    em_uso = df[df["SITUACAO_NORMALIZADA"] == "Em Uso"]["VALOR_TOTAL"].sum()
    danificados = df[df["ESTADO_NORMALIZADO"].str.contains("Danificado", case=False, na=False)]["VALOR_TOTAL"].sum()
    return {
        "total_registros": int(len(df)),
        "quantidade_total": int(df["QUANTIDADE"].sum()),
        "valor_total": float(valor_total),
        "valor_em_uso": float(em_uso),
        "valor_danificado": float(danificados),
        "categorias_unicas": int(df["CATEGORIA_NORMALIZADA"].nunique()),
    }


def agrupar_por_categoria(df: pd.DataFrame, limite: int = 12) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    agrupado = (
        df.groupby("CATEGORIA_NORMALIZADA")
        .agg(
            Itens=("QUANTIDADE", "sum"),
            Valor_Total=("VALOR_TOTAL", "sum"),
        )
        .reset_index()
        .rename(columns={"CATEGORIA_NORMALIZADA": "Categoria"})
        .sort_values(by="Valor_Total", ascending=False)
    )
    if limite:
        return agrupado.head(limite)
    return agrupado


def agrupar_por_estado(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("ESTADO_NORMALIZADO")
        .agg(
            Itens=("QUANTIDADE", "sum"),
            Valor_Total=("VALOR_TOTAL", "sum"),
        )
        .reset_index()
        .rename(columns={"ESTADO_NORMALIZADO": "Estado"})
        .sort_values(by="Itens", ascending=False)
    )


def agrupar_por_situacao(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("SITUACAO_NORMALIZADA")
        .agg(Itens=("QUANTIDADE", "sum"))
        .reset_index()
        .rename(columns={"SITUACAO_NORMALIZADA": "Situação"})
        .sort_values(by="Itens", ascending=False)
    )


def evolucao_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "DATA_ATUALIZACAO" not in df.columns:
        return pd.DataFrame()
    base = df.dropna(subset=["DATA_ATUALIZACAO"]).copy()
    if base.empty:
        return pd.DataFrame()
    base["MES"] = base["DATA_ATUALIZACAO"].dt.to_period("M").astype(str)
    agrupado = (
        base.groupby("MES")
        .agg(
            Atualizacoes=("CODIGO", "count"),
            Valor_Total=("VALOR_TOTAL", "sum"),
        )
        .reset_index()
        .sort_values("MES")
    )
    return agrupado


def top_itens_por_valor(df: pd.DataFrame, limite: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    colunas_padrao = ["ITEM", "CATEGORIA", "MARCA", "MODELO", "QUANTIDADE", "PRECO_ESTIMADO", "VALOR_TOTAL", "ESTADO"]
    disponiveis = [c for c in colunas_padrao if c in df.columns]
    return df.sort_values(by="VALOR_TOTAL", ascending=False).head(limite)[disponiveis]
