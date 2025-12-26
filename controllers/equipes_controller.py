from typing import Dict, List, Tuple
import os
import pandas as pd

from utils.firebase_utils import init_firestore
from models.equipes_model import (
    formatar_equipe_para_firestore,
    slugify_equipe_nome,
)


db = init_firestore()

COLLECTION_MEMBROS = "membros_gp"
COLLECTION_EQUIPES = "equipes_gp"
CSV_PATH = os.path.join("data", "membros_gp", "tratados", "membros_gp_tratados_.csv")


def _split_equipes(value: str) -> List[str]:
    if not value:
        return []
    # Campo pode vir com múltiplas equipes separadas por ';'
    return [e.strip() for e in str(value).split(";") if e.strip()]


def _status_normalizado(status: str) -> str:
    s = str(status or "").strip().lower()
    if s == "ativo":
        return "Ativo"
    if s == "inativo":
        return "Inativo"
    return "Pendente"


def _agrupar_equipes_por_membros() -> pd.DataFrame:
    """Agrupa membros por equipe, retornando métricas por equipe.

    Colunas: EQUIPE, Membros Ativos, Membros Inativos, Total, Orientadores
    """
    membros = db.collection(COLLECTION_MEMBROS).stream()
    stats: Dict[str, Dict[str, object]] = {}

    for doc in membros:
        d = doc.to_dict() or {}
        equipes = _split_equipes(d.get("EQUIPE DE PROJETO", ""))
        if not equipes:
            continue
        status = _status_normalizado(d.get("STATUS", ""))
        orientador = str(d.get("ORIENTADOR", "")).strip()
        for equipe in equipes:
            if equipe not in stats:
                stats[equipe] = {
                    "EQUIPE": equipe,
                    "Membros Ativos": 0,
                    "Membros Inativos": 0,
                    "Total": 0,
                    "_orientadores": set(),
                }
            item = stats[equipe]
            item["Total"] = int(item["Total"]) + 1
            if status == "Ativo":
                item["Membros Ativos"] = int(item["Membros Ativos"]) + 1
            elif status == "Inativo":
                item["Membros Inativos"] = int(item["Membros Inativos"]) + 1
            if orientador:
                item["_orientadores"].add(orientador)

    # Converte para DataFrame e computa Status e Orientadores
    lista: List[Dict[str, object]] = []
    for v in stats.values():
        ativos = int(v.get("Membros Ativos", 0))
        status_eq = "Ativa" if ativos >= 2 else "Inativa"
        orientadores = ", ".join(sorted(v.get("_orientadores", set())))
        lista.append(
            {
                "EQUIPE": v["EQUIPE"],
                "Membros Ativos": ativos,
                "Membros Inativos": int(v.get("Membros Inativos", 0)),
                "Total": int(v.get("Total", 0)),
                "Status": status_eq,
                "Orientadores": orientadores,
            }
        )

    if not lista:
        return pd.DataFrame(columns=[
            "EQUIPE",
            "Membros Ativos",
            "Membros Inativos",
            "Total",
            "Status",
            "Orientadores",
        ])
    return pd.DataFrame(lista).sort_values(by=["Membros Ativos", "Total"], ascending=[False, False]).reset_index(drop=True)


def listar_equipes_firestore() -> pd.DataFrame:
    """Lista equipes combinando a coleção de equipes com as métricas derivadas dos membros."""
    # Deriva métricas a partir dos membros
    df_stats = _agrupar_equipes_por_membros()

    # Carrega equipes cadastradas explicitamente (podem existir mesmo sem membros)
    docs = list(db.collection(COLLECTION_EQUIPES).stream())
    equipes_explicit: Dict[str, Dict[str, object]] = {}
    for doc in docs:
        d = doc.to_dict() or {}
        nome = d.get("NOME") or d.get("nome")
        if not nome:
            continue
        equipes_explicit[nome] = d

    if df_stats.empty and not equipes_explicit:
        return df_stats

    # Une por nome de equipe
    linhas: Dict[str, Dict[str, object]] = {}
    for _, row in df_stats.iterrows():
        linhas[row["EQUIPE"]] = dict(row)

    for nome, data in equipes_explicit.items():
        if nome in linhas:
            # Completa Status com o explícito se existir
            if data.get("STATUS"):
                linhas[nome]["Status"] = data.get("STATUS")
            # Completa Orientador se não houver
            if data.get("ORIENTADOR") and not linhas[nome].get("Orientadores"):
                linhas[nome]["Orientadores"] = data.get("ORIENTADOR")
        else:
            # Equipe sem membros ainda
            linhas[nome] = {
                "EQUIPE": nome,
                "Membros Ativos": 0,
                "Membros Inativos": 0,
                "Total": 0,
                "Status": data.get("STATUS", "Inativa"),
                "Orientadores": data.get("ORIENTADOR", ""),
            }

    return pd.DataFrame(linhas.values()).sort_values(by=["Membros Ativos", "Total"], ascending=[False, False]).reset_index(drop=True)


def salvar_equipe_firestore(dados: Dict[str, object]) -> Tuple[str, Dict[str, object]]:
    """Cria/atualiza uma equipe na coleção de equipes.

    Retorna (doc_id, dados_formatados).
    """
    dados_fmt = formatar_equipe_para_firestore(dados.copy())
    slug = slugify_equipe_nome(dados_fmt.get("NOME", ""))
    if not slug:
        raise ValueError("Nome da equipe é obrigatório")
    db.collection(COLLECTION_EQUIPES).document(slug).set(dados_fmt)
    return slug, dados_fmt


def deletar_equipe(nome_ou_slug: str, cascade: bool = False, desassociar: bool = False) -> None:
    """Remove a equipe da coleção de equipes.

    - cascade=True: remove também os membros associados à equipe.
    - desassociar=True: apenas remove a referência da equipe nos membros (não deleta membros).
    """
    slug = slugify_equipe_nome(nome_ou_slug)
    # Apaga doc de equipe (se existir)
    db.collection(COLLECTION_EQUIPES).document(slug).delete()

    if not (cascade or desassociar):
        return

    # Opera sobre membros da equipe
    from controllers.membros_controller import deletar_membro  # import pontual para evitar ciclos

    membros = db.collection(COLLECTION_MEMBROS).stream()
    for doc in membros:
        d = doc.to_dict() or {}
        equipes = _split_equipes(d.get("EQUIPE DE PROJETO", ""))
        if not equipes:
            continue
        nome_alvo = nome_ou_slug.strip()
        if nome_alvo not in equipes:
            continue
        if cascade:
            deletar_membro(doc.id)
        elif desassociar:
            # Remove apenas a equipe do campo, mantendo demais
            novas = [e for e in equipes if e != nome_alvo]
            novo_valor = ";".join(novas)
            db.collection(COLLECTION_MEMBROS).document(doc.id).update({"EQUIPE DE PROJETO": novo_valor})


def listar_equipes_cadastradas() -> pd.DataFrame:
    """Lista apenas as equipes explicitamente cadastradas na coleção de equipes."""
    docs = db.collection(COLLECTION_EQUIPES).stream()
    lista = []
    for doc in docs:
        item = doc.to_dict() or {}
        item["ID"] = doc.id
        lista.append(item)
    return pd.DataFrame(lista)
