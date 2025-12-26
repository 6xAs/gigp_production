from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from controllers.equipes_controller import listar_equipes_firestore
from controllers.membros_controller import listar_membros_firestore
from controllers.patrimonio_controller import listar_patrimonios
from models.membro_model import carregar_membros_csv
from models.patrimonio_model import carregar_patrimonios_csv


@st.cache_data(ttl=120, show_spinner=False)
def _carregar_membros() -> pd.DataFrame:
    try:
        df = listar_membros_firestore()
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Sem dados do Firestore")
    except Exception:
        df = carregar_membros_csv()
        if df.empty:
            return pd.DataFrame()

    df = df.copy().fillna("")
    if "PROJETO ATUAL" not in df.columns:
        df["PROJETO ATUAL"] = ""
    return df


@st.cache_data(ttl=120, show_spinner=False)
def _carregar_equipes() -> pd.DataFrame:
    try:
        df = listar_equipes_firestore()
    except Exception:
        return pd.DataFrame()
    return df.copy().fillna("")


def _agrupar_projetos(df_membros: pd.DataFrame) -> pd.DataFrame:
    if df_membros.empty or "PROJETO ATUAL" not in df_membros.columns:
        return pd.DataFrame()

    df = df_membros.copy()
    df["PROJETO ATUAL"] = df["PROJETO ATUAL"].astype(str).str.strip()
    df = df[df["PROJETO ATUAL"] != ""]
    if df.empty:
        return pd.DataFrame()

    agrupado = (
        df.groupby("PROJETO ATUAL")
        .agg(
            Total=("CPF", "nunique"),
            Ativos=("STATUS", lambda s: int((s == "Ativo").sum())),
            Inativos=("STATUS", lambda s: int((s == "Inativo").sum())),
            Pendentes=("STATUS", lambda s: int((s == "Pendente").sum())),
            Equipes=(
                "EQUIPE DE PROJETO",
                lambda s: s.replace("", pd.NA).dropna().nunique(),
            ),
        )
        .reset_index()
        .rename(columns={"PROJETO ATUAL": "Projeto"})
    )
    return agrupado.sort_values(by="Total", ascending=False).reset_index(drop=True)


def _metric_or_dash(value, label, help=None):
    st.metric(label, value if value not in (None, "") else "—", help=help, border=True)


def _format_currency(valor: float | int) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def dash_home():
    st.markdown(
        """
        <style>
            .main { background-color: #111111; color: #FFFFFF; }
            .stButton>button { background-color: #1f78d1; color: #FFFFFF; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.image("assets/images/logo_gp/logo_gp_mecatronica.png", use_container_width=True)
    st.sidebar.header("Filtros globais")
    filtro_mes = st.sidebar.selectbox(
        "Mês",
        [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        ],
        index=datetime.now().month - 1,
    )
    filtro_ano = st.sidebar.selectbox("Ano", ["2026", "2025", "2024", "2023"], index=1)
    filtro_departamentos = st.sidebar.multiselect(
        "Departamento",
        ["Pesquisa", "Extensão", "Ensino", "TI"],
        default=["Pesquisa", "Ensino"],
    )
    st.sidebar.slider("% Conclusão Projetos", 0, 100, (30, 80))
    st.sidebar.markdown("---")

    st.markdown("### 📊 Painel Geral – GP Mecatrônica")
    top_col1, top_col2 = st.columns([1, 5])
    if top_col1.button("🔄 Recarregar dados", use_container_width=True):
        try:
            st.cache_data.clear()
        finally:
            st.rerun()

    with st.spinner("Carregando indicadores..."):
        df_membros = _carregar_membros()
        df_equipes = _carregar_equipes()
        df_projetos = _agrupar_projetos(df_membros)
        try:
            df_patrimonio = listar_patrimonios()
        except Exception:
            df_patrimonio = carregar_patrimonios_csv()

    total_membros = len(df_membros)
    membros_ativos = int((df_membros.get("STATUS", pd.Series()) == "Ativo").sum())
    membros_pendentes = int((df_membros.get("STATUS", pd.Series()) == "Pendente").sum())
    orientadores_unicos = (
        df_membros.get("ORIENTADOR", pd.Series()).replace("", pd.NA).dropna().nunique()
        if not df_membros.empty
        else 0
    )

    total_equipes = int(df_equipes.get("EQUIPE", pd.Series()).replace("", pd.NA).dropna().nunique())
    equipes_ativas = int((df_equipes.get("Status", pd.Series()) == "Ativa").sum())
    total_projetos = len(df_projetos)
    projetos_com_ativos = int((df_projetos.get("Ativos", pd.Series()) > 0).sum()) if not df_projetos.empty else 0
    status_palette = {
        "Ativo": "#34a853",
        "Inativo": "#f8b4b4",
        "Pendente": "#fbbc04",
        "Ativa": "#34a853",
        "Inativa": "#f8b4b4",
    }

    st.markdown("#### Indicadores chave")
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        _metric_or_dash(str(total_membros), "👥 Membros cadastrados")
    with mc2:
        _metric_or_dash(str(membros_ativos), "✅ Membros ativos")
    with mc3:
        _metric_or_dash(str(membros_pendentes), "🕒 Membros pendentes")
    with mc4:
        _metric_or_dash(str(orientadores_unicos), "👩‍🏫 Orientadores")

    valor_patrimonio = df_patrimonio["VALOR_TOTAL"].sum() if not df_patrimonio.empty else 0
    mc5, mc6, mc7, mc8 = st.columns(4)
    with mc5:
        _metric_or_dash(str(total_equipes), "🧩 Equipes mapeadas")
    with mc6:
        _metric_or_dash(str(equipes_ativas), "🔥 Equipes ativas")
    with mc7:
        _metric_or_dash(str(total_projetos), "📂 Projetos monitorados")
    with mc8:
        _metric_or_dash(_format_currency(valor_patrimonio), "📦 Patrimônios", help="Valor monetário estimado do inventário")

    st.markdown("---")

    tab_membros, tab_equipes, tab_projetos, tab_patrimonio = st.tabs([
        "👥 Membros",
        "🧩 Equipes",
        "📂 Projetos",
        "📦 Patrimônios",
    ])

    with tab_membros:
        if df_membros.empty:
            st.info("Sem dados de membros disponíveis.")
        else:
            col_a, col_b = st.columns(2)
            status_counts = df_membros.get("STATUS", pd.Series()).value_counts().reset_index()
            status_counts.columns = ["Status", "Total"]
            if not status_counts.empty:
                fig_status = px.bar(
                    status_counts,
                    x="Status",
                    y="Total",
                    color="Status",
                    text_auto=True,
                    title="Distribuição por status",
                    color_discrete_map=status_palette,
                )
                fig_status.update_traces(textangle=0, textposition="outside")
                col_a.plotly_chart(fig_status, use_container_width=True)

            rank_counts = (
                df_membros.get("Rank GP", pd.Series())
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .reset_index()
            )
            rank_counts.columns = ["Rank GP", "Total"]
            if not rank_counts.empty:
                fig_rank = px.bar(
                    rank_counts,
                    x="Rank GP",
                    y="Total",
                    text_auto=True,
                    title="Distribuição de rank",
                    color="Rank GP",
                )
                fig_rank.update_traces(textposition="outside")
                col_b.plotly_chart(fig_rank, use_container_width=True)

            col_c, col_d = st.columns(2)
            orientadores_top = (
                df_membros.get("ORIENTADOR", pd.Series())
                .replace(["", "Não Informado", "Não informado"], pd.NA)
                .dropna()
                .value_counts()
                .head(10)
                .reset_index()
            )
            orientadores_top.columns = ["Orientador", "Membros"]
            if not orientadores_top.empty:
                fig_orientador = px.bar(
                    orientadores_top,
                    x="Membros",
                    y="Orientador",
                    orientation="h",
                    text_auto=True,
                    title="Top orientadores por membros",
                    color="Membros",
                    color_continuous_scale="Blues",
                )
                fig_orientador.update_layout(yaxis_categoryorder="total ascending")
                col_c.plotly_chart(fig_orientador, use_container_width=True)

            curso_top = (
                df_membros.get("CURSO", pd.Series())
                .replace(["", "Não Informado", "Não informado"], pd.NA)
                .dropna()
                .value_counts()
                .head(10)
                .reset_index()
            )
            curso_top.columns = ["Curso", "Membros"]
            if not curso_top.empty:
                fig_curso = px.pie(
                    curso_top,
                    names="Curso",
                    values="Membros",
                    hole=0.45,
                    title="Top 10 cursos dos membros",
                    color_discrete_sequence=px.colors.sequential.Bluered,
                )
                col_d.plotly_chart(fig_curso, use_container_width=True)

            evolucao = pd.DataFrame()
            if "DATA CADASTRO" in df_membros.columns:
                try:
                    evolucao = (
                        pd.to_datetime(df_membros["DATA CADASTRO"], errors="coerce")
                        .dropna()
                        .to_series()
                        .dt.to_period("M")
                        .value_counts()
                        .sort_index()
                        .reset_index()
                    )
                    evolucao.columns = ["Mês", "Novos"]
                    evolucao["Mês"] = evolucao["Mês"].astype(str)
                except Exception:
                    evolucao = pd.DataFrame()
            if not evolucao.empty:
                col_e, _ = st.columns([2, 1])
                fig_evolucao = px.area(
                    evolucao,
                    x="Mês",
                    y="Novos",
                    title="Novos cadastros por mês",
                    color_discrete_sequence=["#7b83ff"],
                )
                fig_evolucao.update_traces(mode="lines+markers")
                col_e.plotly_chart(fig_evolucao, use_container_width=True)

            st.markdown("### Vista rápida")
            st.dataframe(
                df_membros[[c for c in [
                    "NOME",
                    "CPF",
                    "STATUS",
                    "EQUIPE DE PROJETO",
                    "PROJETO ATUAL",
                    "Rank GP",
                ] if c in df_membros.columns]].head(20),
                use_container_width=True,
                hide_index=True,
            )

    with tab_equipes:
        if df_equipes.empty:
            st.info("Nenhuma equipe encontrada.")
        else:
            col_e, col_f = st.columns(2)
            resumo_equipes = df_equipes[[c for c in ["Status", "Total"] if c in df_equipes.columns]]
            if not resumo_equipes.empty and "Status" in resumo_equipes.columns:
                status_eq = resumo_equipes.groupby("Status")["Total"].sum().reset_index()
                fig_eq_status = px.bar(
                    status_eq,
                    x="Status",
                    y="Total",
                    text_auto=True,
                    title="Membros por status da equipe",
                    color="Status",
                    color_discrete_map=status_palette,
                )
                fig_eq_status.update_traces(textposition="outside")
                col_e.plotly_chart(fig_eq_status, use_container_width=True)

            if {"Membros Ativos", "Membros Inativos", "Total"}.issubset(df_equipes.columns):
                dispersao_equipes = df_equipes.sort_values(by="Membros Ativos", ascending=False).head(20)
            else:
                dispersao_equipes = pd.DataFrame()
            if not dispersao_equipes.empty:
                fig_top_eq = px.scatter(
                    dispersao_equipes,
                    x="Membros Ativos",
                    y="Membros Inativos",
                    size="Total",
                    color="Status" if "Status" in dispersao_equipes.columns else None,
                    hover_name="EQUIPE",
                    title="Equipes por atividade",
                    color_discrete_map=status_palette,
                )
                fig_top_eq.update_layout(xaxis_title="Membros ativos", yaxis_title="Membros inativos")
                col_f.plotly_chart(fig_top_eq, use_container_width=True)

            st.markdown("### Equipes em destaque")
            mostrar = df_equipes[[c for c in [
                "EQUIPE",
                "Membros Ativos",
                "Membros Inativos",
                "Total",
                "Status",
                "Orientadores",
            ] if c in df_equipes.columns]].head(15)
            st.dataframe(mostrar, use_container_width=True, hide_index=True)

    with tab_projetos:
        if df_projetos.empty:
            st.info("Nenhum projeto informado pelos membros até o momento.")
        else:
            col_g, col_h = st.columns(2)
            value_vars = [c for c in ["Ativos", "Inativos", "Pendentes"] if c in df_projetos.columns]
            projetos_stack = pd.DataFrame()
            if value_vars:
                projetos_stack = df_projetos.melt(
                    id_vars="Projeto",
                    value_vars=value_vars,
                    var_name="Status",
                    value_name="Quantidade",
                )
            if not projetos_stack.empty:
                fig_proj_status = px.treemap(
                    projetos_stack,
                    path=["Projeto", "Status"],
                    values="Quantidade",
                    color="Status",
                    color_discrete_map=status_palette,
                    title="Distribuição de status por projeto",
                )
                col_g.plotly_chart(fig_proj_status, use_container_width=True)

            rank_proj = pd.DataFrame()
            if {"PROJETO ATUAL", "Rank GP"}.issubset(df_membros.columns):
                rank_proj = (
                    df_membros[["PROJETO ATUAL", "Rank GP"]]
                    .replace({"PROJETO ATUAL": {"": pd.NA}, "Rank GP": {"": pd.NA}})
                    .dropna()
                    .groupby(["PROJETO ATUAL", "Rank GP"])
                    .size()
                    .reset_index(name="Qtd")
                    .rename(columns={"PROJETO ATUAL": "Projeto"})
                )
            if not rank_proj.empty:
                fig_rank_proj = px.scatter(
                    rank_proj,
                    x="Projeto",
                    y="Qtd",
                    size="Qtd",
                    color="Rank GP",
                    title="Ranks distribuídos por projeto",
                )
                fig_rank_proj.update_layout(xaxis_tickangle=-30, yaxis_title="Quantidade")
                col_h.plotly_chart(fig_rank_proj, use_container_width=True)

            st.markdown("### Projetos monitorados")
            st.dataframe(
                df_projetos.head(15),
                use_container_width=True,
                hide_index=True,
            )

    with tab_patrimonio:
        if df_patrimonio.empty:
            st.info("Sem dados de patrimônio disponíveis.")
        else:
            col_p1, col_p2 = st.columns(2)
            patrimonio_estado = (
                df_patrimonio.groupby("ESTADO")
                .agg(Itens=("QUANTIDADE", "sum"), Valor=("VALOR_TOTAL", "sum"))
                .reset_index()
                .sort_values(by="Itens", ascending=False)
            )
            if not patrimonio_estado.empty:
                fig_p_estado = px.bar(
                    patrimonio_estado,
                    x="ESTADO",
                    y="Itens",
                    text_auto=True,
                    title="Itens por estado de conservação",
                    color="ESTADO",
                )
                col_p1.plotly_chart(fig_p_estado, use_container_width=True)

            patrimonio_categoria = (
                df_patrimonio.groupby("CATEGORIA")
                .agg(Valor=("VALOR_TOTAL", "sum"))
                .reset_index()
                .sort_values(by="Valor", ascending=False)
                .head(12)
            )
            if not patrimonio_categoria.empty:
                fig_p_cat = px.pie(
                    patrimonio_categoria,
                    names="CATEGORIA",
                    values="Valor",
                    hole=0.45,
                    title="Top categorias por valor acumulado",
                )
                col_p2.plotly_chart(fig_p_cat, use_container_width=True)

            st.markdown("### Inventário resumido")
            colunas_inv = [
                "CODIGO",
                "ITEM",
                "CATEGORIA",
                "MARCA",
                "QUANTIDADE",
                "PRECO_ESTIMADO",
                "VALOR_TOTAL",
                "ESTADO",
                "SITUACAO_USO",
                "DATA_ATUALIZACAO_BR",
                "DATA_ATUALIZACAO",
            ]
            df_inv = df_patrimonio[[c for c in colunas_inv if c in df_patrimonio.columns]].head(20).copy()
            if "PRECO_ESTIMADO" in df_inv.columns:
                df_inv["PRECO_ESTIMADO"] = df_inv["PRECO_ESTIMADO"].apply(_format_currency)
            if "VALOR_TOTAL" in df_inv.columns:
                df_inv["VALOR_TOTAL"] = df_inv["VALOR_TOTAL"].apply(_format_currency)
            if "DATA_ATUALIZACAO_BR" in df_inv.columns:
                df_inv.rename(columns={"DATA_ATUALIZACAO_BR": "DATA ATUALIZAÇÃO"}, inplace=True)
            if "DATA_ATUALIZACAO" in df_inv.columns:
                df_inv = df_inv.drop(columns=["DATA_ATUALIZACAO"])
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            st.caption(
                "Dados sincronizados com o Firestore; em caso de indisponibilidade é utilizado o arquivo `data/patrimonio_gp/gerenciamento_patrimonial_producao.csv`."
            )

    st.markdown("---")
    ano_atual = datetime.now().year
    st.caption(f"📌 Desenvolvido por: GP Mecatrônica - IFRO Calama • {ano_atual}")
