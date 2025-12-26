import streamlit as st
import pandas as pd
import plotly.express as px
from controllers.membros_controller import listar_membros_firestore, remover_projetos


CSV_PATH = "data/membros_gp/tratados/membros_gp_tratados_.csv"

ORIENTADORES_FIXOS = [
    "ANDERSON SEIXAS",
    "CAMILA SERRÃO",
    "DANIELA TODA",
    "FERNANDO DALL IGNA",
    "LEONARDO FERRAZI",
    "WILLIANS DE PAULA",
    "SABRINA FELICIANO",
    "CLEDENILSON SOUZA",
]


def _normalize_text(value: str) -> str:
    import unicodedata

    if value is None:
        return ""
    return (
        unicodedata.normalize("NFKD", str(value))
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .strip()
        .lower()
    )


def _extras_opcoes():
    return st.session_state.setdefault(
        "opcoes_textuais_extras",
        {"EQUIPE DE PROJETO": [], "PROJETO ATUAL": [], "ORIENTADOR": []},
    )


def _add_extra(campo: str, valor: str):
    extras = _extras_opcoes()
    chave = _normalize_text(valor)
    if not chave:
        return
    atuais = extras.setdefault(campo, [])
    if chave not in [_normalize_text(v) for v in atuais]:
        atuais.append(valor.strip())
    st.session_state["opcoes_textuais_extras"] = extras
    return valor.strip()


def _dialog_novo_projeto():
    @st.dialog("➕ Cadastrar novo projeto")
    def modal():
        df_base = carregar_membros_para_projetos()
        extras = _extras_opcoes()
        equipes_opts = sorted(
            set(
                df_base.get("EQUIPE DE PROJETO", pd.Series()).dropna().astype(str).str.strip().unique().tolist()
                + extras.get("EQUIPE DE PROJETO", [])
            )
        )
        orientadores_opts = ORIENTADORES_FIXOS
        with st.form("form_novo_projeto"):
            nome = st.text_input("Nome do projeto *", placeholder="Digite o nome do projeto")
            equipe_sel = st.multiselect(
                "Equipe(s) relacionada(s)",
                equipes_opts,
                help="Selecione equipes existentes",
            )
            equipe_nova = st.text_input("Adicionar equipe(s) nova(s)", placeholder="Separe por vírgulas")
            orientador_sel = st.multiselect(
                "Orientador(es) (opcional)",
                orientadores_opts,
                help="Selecione orientadores",
            )
            obs = st.text_area("Observações (opcional)")
            enviar = st.form_submit_button("Salvar projeto")
            if enviar:
                if not nome.strip():
                    st.error("Informe o nome do projeto.")
                    return
                nome_final = _add_extra("PROJETO ATUAL", nome)
                equipes_total = []
                for e in equipe_sel + [v.strip() for v in (equipe_nova.split(",") if equipe_nova else []) if v.strip()]:
                    if e and _normalize_text(e) not in [_normalize_text(x) for x in equipes_total]:
                        equipes_total.append(e)
                        _add_extra("EQUIPE DE PROJETO", e)
                orientadores_total = orientador_sel
                # Persiste no Firestore como placeholder para preencher no cadastro de membros
                try:
                    st.toast("Salvando no Firestore...", icon="⌛")
                    from controllers.membros_controller import salvar_membro_firestore
                    salvar_membro_firestore({
                        "CPF": f"proj-{_normalize_text(nome_final)[:40]}",
                        "PROJETO ATUAL": nome_final,
                        "NOME": f"Projeto: {nome_final}",
                        "STATUS": "Pendente",
                        "TIPO MEMBRO": "Projeto",
                    })
                except Exception:
                    pass
                # Cria equipes informadas na coleção de equipes
                if equipes_total:
                    try:
                        from controllers.equipes_controller import salvar_equipe_firestore
                        for nome_eq in equipes_total:
                            salvar_equipe_firestore({
                                "NOME": nome_eq,
                                "STATUS": "Ativa",
                                "ORIENTADOR": ", ".join(orientadores_total),
                            })
                    except Exception:
                        pass
                st.session_state["toast_projetos"] = {"text": "Projeto cadastrado!", "icon": "✅"}
                st.success("Projeto registrado e disponibilizado para cadastro de membros.")
                st.rerun()

    modal()


@st.cache_data(show_spinner=False, ttl=60)
def carregar_membros_para_projetos() -> pd.DataFrame:
    try:
        df = listar_membros_firestore()
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Sem dados do Firestore")
    except Exception:
        try:
            df = pd.read_csv(CSV_PATH)
        except Exception:
            return pd.DataFrame()

    if "PROJETO ATUAL" not in df.columns:
        df["PROJETO ATUAL"] = ""
    return df.fillna("")


def _agrupar_por_projeto(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    agrupado = (
        df.groupby("PROJETO ATUAL")
        .agg(
            TOTAL_MEMBROS=("CPF", "nunique"),
            ATIVOS=("STATUS", lambda s: int((s == "Ativo").sum())),
            INATIVOS=("STATUS", lambda s: int((s == "Inativo").sum())),
            PENDENTES=("STATUS", lambda s: int((s == "Pendente").sum())),
            EQUIPES=(
                "EQUIPE DE PROJETO",
                lambda s: s.replace("", pd.NA).dropna().nunique(),
            ),
            ORIENTADORES=(
                "ORIENTADOR",
                lambda s: s.replace("", pd.NA).dropna().nunique(),
            ),
        )
        .reset_index()
        .sort_values(by=["TOTAL_MEMBROS", "ATIVOS"], ascending=[False, False])
    )

    agrupado.rename(columns={"PROJETO ATUAL": "Projeto"}, inplace=True)
    return agrupado


def gestao_projetos():
    st.markdown("# Gestão de Projetos em Andamento")
    st.caption("Visão consolidada dos projetos informados pelos membros")
    msg = st.session_state.pop("toast_projetos", None)
    if msg:
        st.toast(msg.get("text", ""), icon=msg.get("icon", "✅"))

    ac1, ac2, _ = st.columns([1, 1, 4])
    if ac1.button("🔄 Recarregar dados"):
        try:
            st.cache_data.clear()
        finally:
            st.rerun()
    if ac2.button("➕ Cadastrar novo projeto"):
        _dialog_novo_projeto()

    df_membros = carregar_membros_para_projetos()
    if df_membros.empty:
        st.warning("Sem dados de membros disponíveis para montar a visão de projetos.")
        return

    df_membros["PROJETO ATUAL"] = df_membros["PROJETO ATUAL"].astype(str).str.strip()
    df_com_projeto = df_membros[df_membros["PROJETO ATUAL"] != ""].copy()
    extras = _extras_opcoes()
    extras_proj = extras.get("PROJETO ATUAL", [])
    extras_eq = extras.get("EQUIPE DE PROJETO", [])
    extras_ori = extras.get("ORIENTADOR", [])

    if df_com_projeto.empty:
        st.info(
            "Nenhum membro possui o campo 'Projeto Atual' preenchido. Atualize os cadastros para visualizar esta área."
        )
        if extras_proj:
            st.caption("Projetos extras disponíveis para cadastro de membros:")
            st.write(", ".join(extras_proj))

    st.sidebar.markdown("### 🔎 Filtros — Projetos")
    busca = st.sidebar.text_input("Buscar por projeto, equipe ou orientador", key="busca_proj")
    status_opcoes = ["Todos", "Ativo", "Inativo", "Pendente"]
    status_sel = st.sidebar.selectbox("Status de membros", status_opcoes, index=0, key="status_proj")
    orientadores = st.sidebar.multiselect(
        "Orientadores",
        sorted(set(df_com_projeto["ORIENTADOR"].replace("", pd.NA).dropna().unique().tolist() + extras_ori)),
        key="orientadores_proj",
    )
    equipes = st.sidebar.multiselect(
        "Equipes",
        sorted(set(df_com_projeto["EQUIPE DE PROJETO"].replace("", pd.NA).dropna().unique().tolist() + extras_eq)),
        key="equipes_proj",
    )

    filtrado = df_com_projeto
    if busca:
        termo = _normalize_text(busca)

        def _match(row):
            campos = [
                row.get("PROJETO ATUAL", ""),
                row.get("EQUIPE DE PROJETO", ""),
                row.get("ORIENTADOR", ""),
            ]
            return any(termo in _normalize_text(c) for c in campos)

        filtrado = filtrado[filtrado.apply(_match, axis=1)]

    if status_sel != "Todos" and "STATUS" in filtrado.columns:
        filtrado = filtrado[filtrado["STATUS"] == status_sel]
    if orientadores:
        filtrado = filtrado[filtrado["ORIENTADOR"].isin(orientadores)]
    if equipes:
        filtrado = filtrado[filtrado["EQUIPE DE PROJETO"].isin(equipes)]

    if filtrado.empty and not extras_proj:
        st.info("Nenhum projeto encontrado com os filtros atuais.")
        return

    if filtrado.empty:
        agrupado = pd.DataFrame(
            columns=["Projeto", "TOTAL_MEMBROS", "ATIVOS", "INATIVOS", "PENDENTES", "EQUIPES", "ORIENTADORES"]
        )
    else:
        agrupado = _agrupar_por_projeto(filtrado)
    if extras_proj:
        existentes = set(agrupado["Projeto"].tolist()) if not agrupado.empty else set()
        for proj in extras_proj:
            if proj not in existentes:
                agrupado = pd.concat(
                    [
                        agrupado,
                        pd.DataFrame(
                            [{
                                "Projeto": proj,
                                "TOTAL_MEMBROS": 0,
                                "ATIVOS": 0,
                                "INATIVOS": 0,
                                "PENDENTES": 0,
                                "EQUIPES": 0,
                                "ORIENTADORES": 0,
                            }]
                        ),
                    ],
                    ignore_index=True,
                )

    total_projetos = len(agrupado)
    projetos_com_ativos = int((agrupado["ATIVOS"] > 0).sum())
    membros_env = int(filtrado["CPF"].nunique()) if not filtrado.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Projetos encontrados", total_projetos, border=True)
    c2.metric("Projetos com membros ativos", projetos_com_ativos, border=True)
    c3.metric("Membros envolvidos", membros_env, border=True)

    st.markdown("## Gerenciar projetos")
    df_gerenciar = agrupado[["Projeto", "TOTAL_MEMBROS", "ATIVOS", "INATIVOS", "PENDENTES"]].copy()
    df_gerenciar = df_gerenciar.set_index("Projeto")
    df_gerenciar.insert(0, "EXCLUIR", False)
    retorno_proj = st.data_editor(
        df_gerenciar,
        num_rows="fixed",
        hide_index=False,
        use_container_width=True,
        column_config={
            "EXCLUIR": st.column_config.CheckboxColumn("Excluir", help="Remove o projeto de todos os membros selecionados"),
            "TOTAL_MEMBROS": st.column_config.NumberColumn("Total"),
            "ATIVOS": st.column_config.NumberColumn("Ativos"),
            "INATIVOS": st.column_config.NumberColumn("Inativos"),
            "PENDENTES": st.column_config.NumberColumn("Pendentes"),
        },
        key="projetos_manager",
    )
    projetos_excluir = [idx for idx, row in retorno_proj.iterrows() if row.get("EXCLUIR")]
    if st.button(
        f"🗑️ Remover projetos selecionados ({len(projetos_excluir)})",
        disabled=len(projetos_excluir) == 0,
        type="secondary",
    ):
        alterados = remover_projetos(projetos_excluir)
        st.toast(f"Projeto(s) removido(s) do cadastro de {alterados} membro(s)", icon="✅")
        st.cache_data.clear()
        st.rerun()

    st.markdown("## Visão Geral")
    st.dataframe(
        agrupado,
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("📊 Insights gerais por projeto", expanded=False):
        status_cols = [c for c in ["ATIVOS", "INATIVOS", "PENDENTES"] if c in agrupado.columns]
        if status_cols:
            fig_status = px.bar(
                agrupado,
                x="Projeto",
                y=status_cols,
                barmode="stack",
                title="Status dos membros por projeto",
            )
            st.plotly_chart(fig_status, use_container_width=True)

        rank_counts = pd.DataFrame()
        if {"Rank GP", "PROJETO ATUAL"}.issubset(filtrado.columns):
            rank_counts = (
                filtrado
                .replace({"Rank GP": {"": pd.NA}})
                .dropna(subset=["Rank GP", "PROJETO ATUAL"])
                .groupby(["PROJETO ATUAL", "Rank GP"])
                .size()
                .reset_index(name="Qtd")
            )
        if not rank_counts.empty:
            fig_rank = px.bar(
                rank_counts,
                x="PROJETO ATUAL",
                y="Qtd",
                color="Rank GP",
                barmode="stack",
                title="Distribuição de Rank por projeto",
            )
            st.plotly_chart(fig_rank, use_container_width=True)

    st.markdown("## Detalhes do Projeto")
    projetos_disponiveis = agrupado["Projeto"].tolist()
    projeto_sel = st.selectbox("Escolha um projeto", projetos_disponiveis, key="projeto_sel")

    detalhes = filtrado[filtrado["PROJETO ATUAL"] == projeto_sel]

    equipes_list = sorted(
        detalhes["EQUIPE DE PROJETO"].replace("", pd.NA).dropna().unique().tolist()
    )
    orient_list = sorted(
        detalhes["ORIENTADOR"].replace("", pd.NA).dropna().unique().tolist()
    )
    equipes_fmt = ", ".join(map(str, equipes_list)) if equipes_list else "Não informado"
    orientadores_fmt = ", ".join(map(str, orient_list)) if orient_list else "Não informado"

    c4, c5 = st.columns([2, 1])
    c4.write(f"**Equipes:** {equipes_fmt}")
    c5.write(f"**Orientadores:** {orientadores_fmt}")

    colunas_detalhes = [
        "NOME",
        "CPF",
        "STATUS",
        "EQUIPE DE PROJETO",
        "ORIENTADOR",
        "TIPO MEMBRO",
        "Rank GP",
    ]
    colunas_existentes = [c for c in colunas_detalhes if c in detalhes.columns]

    abas = st.tabs(["Status", "Rank", "Tipos de Membro"])

    with abas[0]:
        contagem_status = (
            detalhes["STATUS"].value_counts().reset_index()
            if "STATUS" in detalhes.columns
            else pd.DataFrame(columns=["STATUS", "count"])
        )
        contagem_status.columns = ["STATUS", "Qtd"]
        if not contagem_status.empty:
            grafico = px.pie(
                contagem_status,
                names="STATUS",
                values="Qtd",
                hole=0.35,
                title="Distribuição por status",
            )
            st.plotly_chart(grafico, use_container_width=True)
        else:
            st.info("Sem dados de status para este projeto.")

    with abas[1]:
        if "Rank GP" in detalhes.columns:
            rank_proj = (
                detalhes.replace({"Rank GP": {"": pd.NA}})
                .dropna(subset=["Rank GP"])
                ["Rank GP"].value_counts().reset_index()
            )
            rank_proj.columns = ["Rank GP", "Qtd"]
            if not rank_proj.empty:
                fig_rank_proj = px.bar(
                    rank_proj,
                    x="Rank GP",
                    y="Qtd",
                    text="Qtd",
                    title="Distribuição de Rank no projeto",
                )
                fig_rank_proj.update_traces(textposition="outside")
                st.plotly_chart(fig_rank_proj, use_container_width=True)
            else:
                st.info("Nenhum rank informado para os membros deste projeto.")
        else:
            st.info("Coluna de Rank não disponível.")

    with abas[2]:
        if {"TIPO MEMBRO", "STATUS"}.issubset(detalhes.columns):
            tipo_status = (
                detalhes.replace({"TIPO MEMBRO": {"": pd.NA}})
                .dropna(subset=["TIPO MEMBRO"])
                .groupby(["TIPO MEMBRO", "STATUS"])
                .size()
                .reset_index(name="Qtd")
            )
            if not tipo_status.empty:
                fig_tipo = px.bar(
                    tipo_status,
                    x="TIPO MEMBRO",
                    y="Qtd",
                    color="STATUS",
                    barmode="group",
                    title="Tipo de membro por status",
                )
                st.plotly_chart(fig_tipo, use_container_width=True)
            else:
                st.info("Sem dados de tipo de membro para este projeto.")
        else:
            st.info("Colunas necessárias para a análise de tipos não estão disponíveis.")

    if colunas_existentes:
        st.markdown("### Lista de Membros")
        st.dataframe(
            detalhes[colunas_existentes],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sem informações tabulares disponíveis para este projeto.")

    st.caption("Dados consolidados automaticamente a partir do cadastro de membros.")
