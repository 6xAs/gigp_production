from utils.firebase_utils import init_firestore
from utils.data_cleaning import clean_members_dataframe
from models.membro_model import formatar_membro_para_firestore
import pandas as pd
import os
import re
from datetime import datetime
from typing import Sequence

db = init_firestore()

COLLECTION = "membros_gp"
CSV_PATH = os.path.join("data", "membros_gp", "tratados", "membros_gp_tratados_.csv")

CAMPOS_PADRAO = list(
    dict.fromkeys(
        [
            "DATA CADASTRO",
            "NOME",
            "CPF",
            "EMAIL",
            "CONTATO",
            "LATTES",
            "MATRÍCULA",
            "TAMANHO CAMISETA",
            "DATA NASCIMENTO",
            "EQUIPE DE PROJETO",
            "ORIENTADOR",
            "SÉRIE",
            "ANO",
            "NÍVEL ESCOLARIDADE",
            "CURSO",
            "STATUS CURSO",
            "ÁREAS DE INTERESSE",
            "Rank GP",
            "TIPO MEMBRO",
            "STATUS",
            "PROJETO ATUAL",
        ]
    )
)

_SINCRONIZACAO_REALIZADA = False

def importar_csv_para_firestore():
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        df = clean_members_dataframe(df)
        for _, row in df.iterrows():
            salvar_membro_firestore(row.to_dict())

def verificar_e_persistir_dados():
    membros = list(db.collection(COLLECTION).stream())
    if not membros:
        importar_csv_para_firestore()

def listar_membros_firestore():
    global _SINCRONIZACAO_REALIZADA
    verificar_e_persistir_dados()
    if not _SINCRONIZACAO_REALIZADA:
        if os.path.exists(CSV_PATH):
            try:
                sincronizar_campos_membros()
            except Exception:
                pass
            else:
                _SINCRONIZACAO_REALIZADA = True
        else:
            _SINCRONIZACAO_REALIZADA = True
    membros = db.collection(COLLECTION).stream()
    lista = []
    for doc in membros:
        item = doc.to_dict()
        item["CPF"] = doc.id
        lista.append(item)
    return pd.DataFrame(lista)

def salvar_membro_firestore(dados):
    doc_id = dados.get("CPF") or dados.get("MATRÍCULA")
    if not doc_id:
        return
    dados_fmt = formatar_membro_para_firestore(dados.copy())
    db.collection(COLLECTION).document(str(doc_id)).set(dados_fmt)

def salvar_dataframe_completo(df):
    for _, row in df.iterrows():
        salvar_membro_firestore(row.to_dict())

def deletar_membro(cpf):
    db.collection(COLLECTION).document(str(cpf)).delete()


def deletar_membros(cpfs: list[str]) -> int:
    if not cpfs:
        return 0
    removidos = 0
    for cpf in cpfs:
        try:
            db.collection(COLLECTION).document(str(cpf)).delete()
            removidos += 1
        except Exception:
            continue
    return removidos


def remover_projetos(projetos: list[str]) -> int:
    if not projetos:
        return 0
    alterados = 0
    for projeto in projetos:
        try:
            docs = db.collection(COLLECTION).where("PROJETO ATUAL", "==", projeto).stream()
        except Exception:
            continue
        for doc in docs:
            try:
                db.collection(COLLECTION).document(doc.id).update({"PROJETO ATUAL": ""})
                alterados += 1
            except Exception:
                continue
    return alterados


def substituir_valor_campo(campo: str, valor_antigo: str, valor_novo: str) -> int:
    """Substitui valor de um campo em todos os documentos que o possuem."""
    try:
        docs = db.collection(COLLECTION).where(campo, "==", valor_antigo).stream()
    except Exception:
        return 0
    alterados = 0
    for doc in docs:
        try:
            db.collection(COLLECTION).document(doc.id).update({campo: valor_novo})
            alterados += 1
        except Exception:
            continue
    return alterados


def _normalizar_chave(valor):
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor.strip().lower()
    return str(valor).strip().lower()


def _normalizar_identificador(valor: str | None) -> str:
    if not valor:
        return ""
    return re.sub(r"[^0-9a-z]", "", _normalizar_chave(valor))


def _sanitize_value(valor):
    if isinstance(valor, (list, dict)):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return valor


def _buscar_valor_csv(row: pd.Series | None, campo: str):
    if row is None:
        return None
    opcoes = [campo, campo.upper(), campo.lower(), campo.title()]
    vistos = set()
    for opcao in opcoes:
        if opcao in vistos:
            continue
        vistos.add(opcao)
        if opcao in row.index:
            return row[opcao]
    return None


def _build_csv_lookup(df: pd.DataFrame) -> dict[str, dict[str, pd.Series]]:
    lookup = {"cpf": {}, "matricula": {}, "email": {}}
    for _, row in df.iterrows():
        cpf = row.get("CPF")
        if cpf:
            lookup["cpf"][_normalizar_identificador(cpf)] = row
        matricula = row.get("MATRÍCULA")
        if matricula:
            lookup["matricula"][_normalizar_identificador(matricula)] = row
        email = row.get("EMAIL")
        if email:
            lookup["email"][_normalizar_identificador(email)] = row
    return lookup


def _localizar_row_csv(lookup: dict[str, dict[str, pd.Series]], dados: dict, doc_id: str):
    cpf = dados.get("CPF") or doc_id
    row = lookup.get("cpf", {}).get(_normalizar_identificador(cpf))
    if row is not None:
        return row
    matricula = dados.get("MATRÍCULA")
    if matricula:
        row = lookup.get("matricula", {}).get(_normalizar_identificador(matricula))
        if row is not None:
            return row
    email = dados.get("EMAIL")
    if email:
        row = lookup.get("email", {}).get(_normalizar_identificador(email))
        if row is not None:
            return row
    return None


def sincronizar_campos_membros(campos_base: Sequence[str] | None = None) -> dict:
    campos = list(dict.fromkeys((campos_base or CAMPOS_PADRAO) + ["PROJETO ATUAL", "DATA CADASTRO"]))

    df_csv = pd.DataFrame()
    if os.path.exists(CSV_PATH):
        try:
            df_csv = pd.read_csv(CSV_PATH)
            df_csv = clean_members_dataframe(df_csv)
        except Exception:
            df_csv = pd.DataFrame()

    lookup = _build_csv_lookup(df_csv) if not df_csv.empty else {"cpf": {}, "matricula": {}, "email": {}}

    documentos = list(db.collection(COLLECTION).stream())
    atualizados: list[str] = []

    for doc in documentos:
        dados = doc.to_dict() or {}
        if "CPF" not in dados or not dados.get("CPF"):
            dados["CPF"] = doc.id
        linha_csv = _localizar_row_csv(lookup, dados, doc.id) if lookup else None
        atualizou = False

        for campo in campos:
            valor_csv = _buscar_valor_csv(linha_csv, campo) if linha_csv is not None else None
            valor_csv = _sanitize_value(valor_csv)
            valor_atual = dados.get(campo)
            valor_atual_sanit = _sanitize_value(valor_atual)

            if valor_csv not in ("", None):
                if valor_atual_sanit != valor_csv:
                    dados[campo] = valor_csv
                    atualizou = True
            else:
                if campo not in dados:
                    dados[campo] = ""
                    atualizou = True
                elif isinstance(valor_atual, (pd.Timestamp, datetime)):
                    dados[campo] = valor_atual_sanit
                    atualizou = True
                elif valor_atual is None:
                    dados[campo] = ""
                    atualizou = True

        if atualizou:
            dados_persistencia = {ch: _sanitize_value(val) for ch, val in dados.items()}
            db.collection(COLLECTION).document(str(doc.id)).set(dados_persistencia, merge=True)
            atualizados.append(doc.id)

    return {
        "total_documentos": len(documentos),
        "atualizados": atualizados,
        "csv_utilizado": not df_csv.empty,
    }
