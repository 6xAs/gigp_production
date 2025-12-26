import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from controllers.equipes_controller import (
    listar_equipes_firestore,
    salvar_equipe_firestore,
    listar_equipes_cadastradas,
)
from controllers.membros_controller import listar_membros_firestore
from views.projetos.view_projetos_dash import _add_extra  # reutiliza registrador de opções globais

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


def _inject_dialog_css():
    st.markdown(
        """
        <style>
        /* Alarga o container do diálogo (estratégias múltiplas) */
        [data-testid="stDialog"],
        [data-testid="stDialog"] > div,
        div[role="dialog"][aria-modal="true"],
        div[role="dialog"][aria-modal="true"] > div {
            width: 95vw !important;
            max-width: 95vw !important;
        }
        /* Bloco interno ocupa toda a largura */
        [data-testid="stDialog"] [data-testid="stVerticalBlock"],
        div[role="dialog"][aria-modal="true"] [data-testid="stVerticalBlock"] {
            width: 100% !important;
            max-width: 95vw !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, ttl=60)
def carregar_equipes_df() -> pd.DataFrame:
    try:
        df = listar_equipes_firestore()
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame(columns=[
                "EQUIPE", "Membros Ativos", "Membros Inativos", "Total", "Status", "Orientadores"
            ])
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "EQUIPE", "Membros Ativos", "Membros Inativos", "Total", "Status", "Orientadores"
        ])


def _indicadores(df: pd.DataFrame) -> None:
    st.subheader("Indicadores de Equipes")
    if df.empty:
        st.info("Sem dados para indicadores.")
        return
    total = len(df)
    ativas = int((df["Status"] == "Ativa").sum()) if "Status" in df.columns else 0
    inativas = int((df["Status"] == "Inativa").sum()) if "Status" in df.columns else 0
    sem_membros = int((df.get("Total", 0) == 0).sum()) if "Total" in df.columns else 0
    orientadores = 0
    if "Orientadores" in df.columns:
        # conta orientadores únicos considerando separador por vírgula
        org_set = set()
        for val in df["Orientadores"].dropna().astype(str):
            for nome in [v.strip() for v in val.split(",") if v.strip()]:
                org_set.add(nome)
        orientadores = len(org_set)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏷️ Equipes", f"{total}", border=True)
    c2.metric("✅ Ativas", f"{ativas}", border=True)
    c3.metric("⏸️ Inativas", f"{inativas}", border=True)
    c4.metric("👨‍🏫 Orientadores", f"{orientadores}", help="Únicos nas equipes", border=True)
    st.caption(f"ℹ️ {sem_membros} equipe(s) sem membros cadastrados.")


def _dialog_cadastro_equipe():
    @st.dialog("➕ Cadastro de Nova Equipe")
    def modal():
        existentes = listar_equipes_cadastradas()
        nomes_existentes = set(existing.strip().lower() for existing in existentes.get("NOME", pd.Series()).astype(str))
        orientadores_opts = ORIENTADORES_FIXOS
        with st.form("form_equipe"):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome da Equipe *", placeholder="Ex.: Equipe Robótica Alpha")
                orientador_sel = st.multiselect(
                    "Orientador Responsável",
                    orientadores_opts,
                    help="Selecione um ou mais orientadores",
                )
            with col2:
                status = st.selectbox("Status", ["Ativa", "Inativa"], index=0)
            descricao = st.text_area("Descrição (opcional)")
            enviar = st.form_submit_button("Salvar Equipe")
            if enviar:
                if not nome:
                    st.error("Informe o nome da equipe.")
                    return
                if nome.strip().lower() in nomes_existentes:
                    st.error("Equipe já cadastrada.")
                    return
                orientadores_total = orientador_sel
                try:
                    salvar_equipe_firestore({
                        "NOME": nome,
                        "ORIENTADOR": ", ".join(orientadores_total),
                        "STATUS": status,
                        "DESCRICAO": descricao,
                    })
                    # adiciona às opções globais de cadastro de membros
                    _add_extra("EQUIPE DE PROJETO", nome)
                    for ori in orientadores_total:
                        _add_extra("ORIENTADOR", ori)
                    st.session_state["toast_equipes"] = {"text": "Equipe cadastrada!", "icon": "✅"}
                    st.success("✅ Equipe salva com sucesso no Firebase!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao salvar equipe: {e}")

    modal()


def _aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sb = st.sidebar
    sb.markdown("### 🔎 Filtros — Equipes")
    busca = sb.text_input("Buscar por nome/ orientador", key="filtro_q_equipes")
    status = sb.selectbox("Status", ["Todos", "Ativa", "Inativa"], index=0, key="filtro_status_equipes")
    orientadores = sorted(
        set(nome.strip() for v in df.get("Orientadores", pd.Series()).dropna().astype(str)
            for nome in v.split(",") if nome.strip())
    )
    ori_sel = sb.multiselect("Orientador", orientadores, key="filtro_orientadores_equipes")

    if sb.button("Limpar filtros"):
        st.session_state["filtro_q_equipes"] = ""
        st.session_state["filtro_status_equipes"] = "Todos"
        st.session_state["filtro_orientadores_equipes"] = []
        st.rerun()

    df2 = df.copy()
    if busca:
        q = busca.strip()
        if q:
            mask = (
                df2["EQUIPE"].astype(str).str.contains(q, case=False, na=False)
                | df2.get("Orientadores", pd.Series(dtype=str)).astype(str).str.contains(q, case=False, na=False)
            )
            df2 = df2[mask]
    if status != "Todos" and "Status" in df2.columns:
        df2 = df2[df2["Status"] == status]
    if ori_sel:
        def has_any(row):
            atual = set(n.strip() for n in str(row.get("Orientadores", "")).split(",") if n.strip())
            return any(o in atual for o in ori_sel)
        df2 = df2[df2.apply(has_any, axis=1)]
    return df2


def _graficos(df: pd.DataFrame) -> None:
    if df.empty:
        return
    with st.expander("📈 Ver gráficos"):
        c1, c2 = st.columns(2)
        if "Status" in df.columns:
            fig1 = px.pie(df, names="Status", title="Status das Equipes", hole=0.35)
            c1.plotly_chart(fig1, use_container_width=True)
        if "Membros Ativos" in df.columns:
            top = df.sort_values(by=["Membros Ativos", "Total"], ascending=[False, False]).head(10)
            fig2 = px.bar(top, x="EQUIPE", y="Membros Ativos", title="Top 10 — Membros Ativos por Equipe")
            c2.plotly_chart(fig2, use_container_width=True)


def gestao_equipes():
    st.markdown("# 🏷️ Gestão de Equipes do GP Mecatrônica")
    msg = st.session_state.pop("toast_equipes", None)
    if msg:
        st.toast(msg.get("text", ""), icon=msg.get("icon", "✅"))

    # Garante CSS do diálogo carregado antes de abrir o modal
    _inject_dialog_css()

    # Barra de ações
    a1, a2, _ = st.columns([1, 1, 6])
    if a1.button("➕ Cadastrar nova equipe"):
        _dialog_cadastro_equipe()
    if a2.button("🔄 Recarregar dados"):
        try:
            st.cache_data.clear()
        finally:
            st.rerun()

    # Dados
    df = carregar_equipes_df()
    if not df.empty and "EQUIPE" in df.columns:
        # Remove equipes não informadas
        mask_valid = ~df["EQUIPE"].astype(str).str.strip().str.lower().isin([
            "nao informado", "não informado", "nao-informado", "nao_informado", ""
        ])
        df = df[mask_valid].reset_index(drop=True)
        # Normaliza Status para apenas "Ativa"/"Inativa" e evita None/blank
        if "Status" in df.columns:
            df["Status"] = df["Status"].fillna("")
            df["Status"] = df["Status"].replace({"Ativo": "Ativa", "Inativo": "Inativa"})
            df["Status"] = df["Status"].where(df["Status"].isin(["Ativa", "Inativa"]), "Inativa")
    if df.empty:
        st.info("Nenhuma equipe encontrada. Cadastre uma nova equipe para começar.")
    else:
        _indicadores(df)

        # Busca principal (vetorizada)
        busca_top = st.text_input("Buscar por nome de equipe ou orientador", key="busca_top_equipes")
        if busca_top:
            q = busca_top.strip()
            if q:
                mask = (
                    df["EQUIPE"].astype(str).str.contains(q, case=False, na=False)
                    | df.get("Orientadores", pd.Series(dtype=str)).astype(str).str.contains(q, case=False, na=False)
                )
                df = df[mask]

        # Filtros (sidebar)
        df_filtrado = _aplicar_filtros(df)

        # Abas por status
        abas = st.tabs(["Todas", "Ativas", "Inativas"])
        status_map = {"Todas": None, "Ativas": "Ativa", "Inativas": "Inativa"}

        for i, nome_tab in enumerate(status_map.keys()):
            with abas[i]:
                df_tab = df_filtrado
                status = status_map[nome_tab]
                if status and "Status" in df_tab.columns:
                    df_tab = df_tab[df_tab["Status"] == status]

                colunas = [c for c in ["EQUIPE", "Orientadores", "Membros Ativos", "Membros Inativos", "Total", "Status"] if c in df_tab.columns]
                df_tab = df_tab[colunas]

                # Paginação fixa de 10 por página
                total_rows = len(df_tab)
                page_size = 10
                total_pages = max(1, (total_rows + page_size - 1) // page_size)
                pn_key = f"pn_eq_{nome_tab}"
                page_num = st.session_state.get(pn_key, 1)
                if page_num > total_pages:
                    st.session_state[pn_key] = total_pages
                    page_num = total_pages

                start = (page_num - 1) * page_size
                end = min(start + page_size, total_rows)
                df_page = df_tab.iloc[start:end].copy()
                # Garante Status válido nesta página para não aparecer opção em branco
                if "Status" in df_page.columns:
                    df_page["Status"] = df_page["Status"].astype(str).fillna("")
                    df_page["Status"] = df_page["Status"].replace({"Ativo": "Ativa", "Inativo": "Inativa", "": "Inativa"})
                    df_page["Status"] = df_page["Status"].where(df_page["Status"].isin(["Ativa", "Inativa"]), "Inativa")

                retorno = st.data_editor(
                    df_page,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "EQUIPE": st.column_config.TextColumn("Equipe", disabled=True),
                        "Orientadores": st.column_config.TextColumn("Orientadores"),
                        "Membros Ativos": st.column_config.NumberColumn("Membros Ativos", disabled=True),
                        "Membros Inativos": st.column_config.NumberColumn("Membros Inativos", disabled=True),
                        "Total": st.column_config.NumberColumn("Total", disabled=True),
                        "Status": st.column_config.SelectboxColumn("Status", options=["Ativa", "Inativa"]),
                    },
                    key=f"editor_equipes_{nome_tab}",
                )

                # Navegação de página
                b_prev, b_next, b_info = st.columns([1, 1, 6])
                prev_disabled = page_num <= 1
                next_disabled = page_num >= total_pages
                if b_prev.button("◀️ Anterior", disabled=prev_disabled, key=f"prev_eq_{nome_tab}"):
                    st.session_state[pn_key] = max(1, page_num - 1)
                    st.rerun()
                if b_next.button("Próxima ▶️", disabled=next_disabled, key=f"next_eq_{nome_tab}"):
                    st.session_state[pn_key] = min(total_pages, page_num + 1)
                    st.rerun()
                b_info.caption(f"Página {page_num}/{total_pages} • Mostrando {start+1}–{end} de {total_rows}")

                # Autosave: detecta e salva alterações imediatamente
                try:
                    campos_editaveis = [c for c in ["Orientadores", "Status"] if c in retorno.columns]
                    if campos_editaveis and not retorno.empty:
                        orig_idx = df_page.set_index("EQUIPE")
                        ret_idx = retorno.set_index("EQUIPE")

                        # Normaliza Status no retorno para garantir apenas duas opções ao salvar
                        if "Status" in ret_idx.columns:
                            ret_idx.loc[:, "Status"] = ret_idx["Status"].astype(str).replace({"": "Inativa"})
                            ret_idx.loc[:, "Status"] = ret_idx["Status"].where(ret_idx["Status"].isin(["Ativa", "Inativa"]), "Inativa")

                        alteradas = []
                        for equipe, row in ret_idx.iterrows():
                            if equipe not in orig_idx.index:
                                continue
                            before = orig_idx.loc[equipe]
                            changed = any(str(row.get(c, "")) != str(before.get(c, "")) for c in campos_editaveis)
                            if changed:
                                alteradas.append(equipe)

                        updated_key = f"updated_eq_{nome_tab}_{page_num}"
                        already = set(st.session_state.get(updated_key, []))
                        to_save = [eq for eq in alteradas if eq not in already]

                        if to_save:
                            ok = 0
                            for eq in to_save:
                                payload = {
                                    "NOME": eq,
                                    "ORIENTADOR": str(ret_idx.loc[eq].get("Orientadores", "")),
                                    "STATUS": str(ret_idx.loc[eq].get("Status", "")),
                                }
                                try:
                                    salvar_equipe_firestore(payload)
                                    ok += 1
                                except Exception as e:
                                    st.warning(f"Falha ao salvar '{eq}': {e}")
                            if ok:
                                st.session_state[updated_key] = list(already.union(to_save))
                                st.toast(f"{ok} equipe(s) atualizada(s)", icon="✅")
                                try:
                                    st.cache_data.clear()
                                except Exception:
                                    pass
                except Exception as e:
                    st.warning(f"Não foi possível verificar alterações: {e}")

        _graficos(df_filtrado)

    st.markdown("---")
    st.caption(f"📌 Desenvolvido por: Equipe Vingadores — GP Mecatrônica - IFRO Calama • {date.today().year}")
