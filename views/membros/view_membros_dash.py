import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from math import ceil
import unicodedata
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

from controllers.membros_controller import (
    deletar_membros,
    listar_membros_firestore,
    salvar_membro_firestore,
    salvar_dataframe_completo,
    substituir_valor_campo,
)
## Limpeza de CSV será feita fora da UI (one-off)

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

CSV_PATH = os.path.join("data/membros_gp/tratados/membros_gp_tratados_.csv")

def normalize_string(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ASCII", "ignore").decode("utf-8").lower()


def _toast_once(key: str):
    msg = st.session_state.pop(key, None)
    if msg:
        st.toast(msg.get("text", ""), icon=msg.get("icon", "✅"))


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


def _avatar_html(nome: str) -> str:
    iniciais = "".join([p[:1] for p in nome.split()[:2]]).upper() or "GP"
    return f"""
    <div style="
        width:64px;height:64px;border-radius:50%;
        background:linear-gradient(135deg,#4c6fff,#22c55e);
        display:flex;align-items:center;justify-content:center;
        color:#fff;font-size:22px;font-weight:700;
        box-shadow:0 6px 16px rgba(76,111,255,0.2);
    ">{iniciais}</div>
    """


def _normalizar_opcao(valor: str) -> str:
    base = normalize_string(valor)
    return " ".join(base.split())


def _validar_e_preparar_membro(
    dados: dict,
    cpfs_existentes: set[str] | None = None,
    emails_existentes: set[str] | None = None,
) -> tuple[dict, list[str]]:
    """Valida campos básicos e normaliza payload para persistência."""
    erros: list[str] = []
    payload = {}

    def _format_cpf(digits: str) -> str:
        if len(digits) != 11:
            return digits
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

    def _format_phone(digits: str) -> str:
        if len(digits) == 11:
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        if len(digits) == 10:
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        return digits

    def _texto(campo: str, obrigatorio: bool = False, max_len: int | None = None):
        valor = (dados.get(campo) or "").strip()
        if obrigatorio and not valor:
            erros.append(f"{campo}: obrigatório")
        if max_len and len(valor) > max_len:
            valor = valor[:max_len]
        payload[campo] = valor

    _texto("NOME", obrigatorio=True, max_len=120)
    _texto("CPF", obrigatorio=True, max_len=20)
    _texto("EMAIL", max_len=120)
    _texto("CONTATO", max_len=60)
    _texto("EQUIPE DE PROJETO", max_len=80)
    _texto("PROJETO ATUAL", max_len=120)
    _texto("ORIENTADOR", max_len=120)
    _texto("CURSO", max_len=120)
    _texto("LATTES", max_len=200)
    _texto("MATRÍCULA", max_len=40)
    _texto("TAMANHO CAMISETA", max_len=5)
    _texto("NÍVEL ESCOLARIDADE", max_len=60)
    _texto("STATUS CURSO", max_len=40)
    _texto("ÁREAS DE INTERESSE", max_len=400)
    _texto("TIPO MEMBRO", max_len=40)
    _texto("Rank GP", max_len=5)
    _texto("STATUS", max_len=20)

    data_nasc = dados.get("DATA NASCIMENTO")
    if data_nasc:
        try:
            payload["DATA NASCIMENTO"] = data_nasc.strftime("%Y-%m-%d")
        except Exception:
            erros.append("DATA NASCIMENTO: data inválida")
    else:
        payload["DATA NASCIMENTO"] = ""

    if payload["CPF"]:
        cpf_digits = "".join(ch for ch in payload["CPF"] if ch.isdigit())
        if len(cpf_digits) not in (11,):
            erros.append("CPF: informe 11 dígitos")
        else:
            if cpfs_existentes and cpf_digits in cpfs_existentes:
                erros.append("CPF já cadastrado")
            payload["CPF"] = _format_cpf(cpf_digits)

    contato_digits = "".join(ch for ch in payload["CONTATO"] if ch.isdigit())
    if contato_digits:
        if len(contato_digits) != 11:
            erros.append("CONTATO: informe 11 dígitos (ex: 99999999999)")
        else:
            payload["CONTATO"] = _format_phone(contato_digits)
    if payload["EMAIL"]:
        if "@" not in payload["EMAIL"]:
            erros.append("EMAIL: formato inválido")
        else:
            email_norm = payload["EMAIL"].lower().strip()
            if emails_existentes and email_norm in emails_existentes:
                erros.append("EMAIL já cadastrado")
            payload["EMAIL"] = email_norm

    return payload, erros

@st.cache_data(show_spinner=False, ttl=60)
def carregar_membros_df():
    try:
        df = listar_membros_firestore()
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Sem dados do Firestore")
        if "PROJETO ATUAL" not in df.columns:
            df["PROJETO ATUAL"] = ""
        return df
    except Exception:
        if os.path.exists(CSV_PATH):
            df_csv = pd.read_csv(CSV_PATH)
            if "PROJETO ATUAL" not in df_csv.columns:
                df_csv["PROJETO ATUAL"] = ""
            return df_csv
        return pd.DataFrame()


def _opcoes_textuais(df: pd.DataFrame) -> dict[str, list[str]]:
    extras = st.session_state.setdefault(
        "opcoes_textuais_extras",
        {"EQUIPE DE PROJETO": [], "PROJETO ATUAL": [], "ORIENTADOR": []},
    )

    def combine(col: str):
        base = sorted(df.get(col, pd.Series()).dropna().astype(str).str.strip().unique().tolist()) if not df.empty else []
        extra = extras.get(col, [])
        vistos = set()
        unidos = []
        for item in base + extra:
            chave = _normalizar_opcao(item)
            if chave and chave not in vistos:
                vistos.add(chave)
                unidos.append(item.strip())
        return unidos

    return {
        "EQUIPE DE PROJETO": combine("EQUIPE DE PROJETO"),
        "PROJETO ATUAL": combine("PROJETO ATUAL"),
        "ORIENTADOR": combine("ORIENTADOR"),
    }


def gerenciar_opcoes_textuais(df: pd.DataFrame):
    with st.expander("⚙️ Gerenciar Equipes, Projetos e Orientadores", expanded=False):
        st.caption("Edite/adicione/remova por coluna; exclusões e renomes aplicam no Firestore.")
        extras = st.session_state.setdefault(
            "opcoes_textuais_extras",
            {"EQUIPE DE PROJETO": [], "PROJETO ATUAL": [], "ORIENTADOR": []},
        )

        opcoes = _opcoes_textuais(df)
        col_eq, col_proj, col_ori = st.columns(3)
        campos_labels = [
            ("EQUIPE DE PROJETO", "Equipe"),
            ("PROJETO ATUAL", "Projeto"),
            ("ORIENTADOR", "Orientador"),
        ]

        for col_ui, (campo, label) in zip([col_eq, col_proj, col_ori], campos_labels):
            with col_ui:
                st.write(f"**{label}s**")
                lista = opcoes.get(campo, [])
                df_edit = pd.DataFrame({"VALOR": lista, "EXCLUIR": False})
                df_edit = st.data_editor(
                    df_edit,
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "VALOR": st.column_config.TextColumn("Valor"),
                        "EXCLUIR": st.column_config.CheckboxColumn("Excluir"),
                    },
                    key=f"editor_{campo}",
                )
                if st.button(f"💾 Salvar {label}s", key=f"save_{campo}"):
                    alterados = 0
                    orig_set = {_normalizar_opcao(v) for v in lista}
                    novos_norm = set()
                    for valor_antigo in lista:
                        # localizar linha correspondente
                        linha = df_edit[df_edit["VALOR"].apply(_normalizar_opcao) == _normalizar_opcao(valor_antigo)]
                        if linha.empty:
                            # removido
                            alterados += substituir_valor_campo(campo, valor_antigo, "")
                            continue
                        novo_valor = linha.iloc[0].get("VALOR", "").strip()
                        excluir = bool(linha.iloc[0].get("EXCLUIR"))
                        if excluir:
                            alterados += substituir_valor_campo(campo, valor_antigo, "")
                        elif novo_valor and novo_valor != valor_antigo:
                            if _normalizar_opcao(novo_valor) in orig_set:
                                st.warning(f"Ignorado renome de '{valor_antigo}' para '{novo_valor}' (já existe).")
                            else:
                                alterados += substituir_valor_campo(campo, valor_antigo, novo_valor)
                    # novos valores (linhas extras)
                    for _, row in df_edit.iterrows():
                        val = (row.get("VALOR") or "").strip()
                        if not val:
                            continue
                        if _normalizar_opcao(val) not in orig_set:
                            if _normalizar_opcao(val) in novos_norm:
                                continue
                            atuais = extras.setdefault(campo, [])
                            if _normalizar_opcao(val) not in [_normalizar_opcao(v) for v in atuais]:
                                atuais.append(val)
                                novos_norm.add(_normalizar_opcao(val))
                    st.session_state["opcoes_textuais_extras"] = extras
                    st.cache_data.clear()
                    st.success(f"{label}s atualizados; {alterados} registro(s) ajustado(s) no Firestore.")
                    st.rerun()

def mostrar_indicadores(df):
    st.subheader("Indicadores Gerais")
    if df.empty:
        st.info("Sem dados para indicadores.")
        return
    status_counts = df["STATUS"].value_counts() if "STATUS" in df.columns else pd.Series()
    total = len(df)
    ativos = int(status_counts.get("Ativo", 0))
    inativos = int(status_counts.get("Inativo", 0))
    pendentes = int(status_counts.get("Pendente", 0))
    equipes = df["EQUIPE DE PROJETO"].nunique() if "EQUIPE DE PROJETO" in df.columns else 0
    projetos = df["PROJETO ATUAL"].nunique() if "PROJETO ATUAL" in df.columns else 0
    orientadores = df["ORIENTADOR"].nunique() if "ORIENTADOR" in df.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👥 Total", f"{total}", border=True)
    c2.metric("✅ Ativos", f"{ativos}", border=True)
    c3.metric("⏸️ Inativos", f"{inativos}", border=True)
    c4.metric("🕒 Pendentes", f"{pendentes}", border=True)
    c5.metric(
        "🧩 Projetos",
        f"{projetos}",
        help="Projetos informados atualmente pelos membros",
        border=True,
    )
    st.caption(f"Equipes únicas: {equipes} • Orientadores únicos: {orientadores}")

def cadastrar_membro():
    @st.dialog("➕ Cadastro de Novo Membro")
    def modal():
        df_base = carregar_membros_df()
        opcoes_texto = _opcoes_textuais(df_base)
        opcoes_equipes = opcoes_texto["EQUIPE DE PROJETO"]
        opcoes_projetos = opcoes_texto["PROJETO ATUAL"]
        opcoes_orientadores = ORIENTADORES_FIXOS
        cpfs_existentes = { "".join(str(cpf).split()).replace(".", "").replace("-", "") for cpf in df_base.get("CPF", pd.Series()).dropna().tolist() } if not df_base.empty else set()
        emails_existentes = { str(email).lower().strip() for email in df_base.get("EMAIL", pd.Series()).dropna().tolist() } if not df_base.empty else set()

        # CSS do modal é injetado globalmente em _inject_dialog_css()
        with st.form("form_membro"):
            col1, col2 = st.columns(2)

            with col1:
                nome = st.text_input("Nome Completo *", placeholder="Digite o nome completo")
                cpf = st.text_input("CPF *", placeholder="000.000.000-00")
                email = st.text_input("Email", placeholder="email@exemplo.com")
                contato = st.text_input("Contato", placeholder="(00) 99999-9999")
                nascimento = st.date_input("Data de Nascimento", format="DD/MM/YYYY", min_value=date(1900, 1, 1), max_value=date.today())
                equipes_sel = st.multiselect(
                    "Equipe(s) de Projeto",
                    opcoes_equipes,
                    help="Selecione uma ou mais equipes existentes",
                )
                equipe_custom_raw = st.text_input(
                    "Adicionar equipe(s) nova(s)",
                    placeholder="Separe por vírgula para múltiplas",
                )
                equipes_custom = [e.strip() for e in equipe_custom_raw.split(",") if e.strip()]
                equipes_total: list[str] = []
                vistos_eq = set()
                for e in equipes_sel + equipes_custom:
                    chave = _normalizar_opcao(e)
                    if chave and chave not in vistos_eq:
                        vistos_eq.add(chave)
                        equipes_total.append(e.strip())
                equipe = ", ".join(equipes_total)

                projetos_sel = st.multiselect(
                    "Projeto(s) Atual(is)",
                    opcoes_projetos,
                    help="Selecione um ou mais projetos existentes",
                )
                projeto_custom_raw = st.text_input(
                    "Adicionar projeto(s) novo(s)",
                    placeholder="Separe por vírgula para múltiplos",
                )
                projetos_custom = [p.strip() for p in projeto_custom_raw.split(",") if p.strip()]
                projetos_total: list[str] = []
                vistos_proj = set()
                for p in projetos_sel + projetos_custom:
                    chave = _normalizar_opcao(p)
                    if chave and chave not in vistos_proj:
                        vistos_proj.add(chave)
                        projetos_total.append(p.strip())
                projeto_atual = ", ".join(projetos_total)

                orientadores_sel = st.multiselect(
                    "Orientador(es)",
                    opcoes_orientadores,
                    help="Selecione um ou mais orientadores existentes",
                )
                orientador_custom_raw = st.text_input(
                    "Adicionar orientador(es) novo(s)",
                    placeholder="Separe por vírgula para múltiplos",
                )
                orientadores_custom = [o.strip() for o in orientador_custom_raw.split(",") if o.strip()]
                orientadores_total = []
                vistos = set()
                for o in orientadores_sel + orientadores_custom:
                    chave = _normalizar_opcao(o)
                    if chave and chave not in vistos:
                        vistos.add(chave)
                        orientadores_total.append(o.strip())
                orientador = ", ".join(orientadores_total)

                curso = st.text_input("Curso")

            with col2:
                lattes = st.text_input("Currículo Lattes", placeholder="URL do currículo Lattes")
                matricula = st.text_input("Matrícula", placeholder="Número de matrícula")
                camiseta = st.selectbox("Tamanho Camiseta", ["P", "M", "G", "GG"])
                escolaridade = st.selectbox("Escolaridade", ["Ensino Médio", "Técnico", "Superior", "Pós-Graduação"])
                status_curso = st.selectbox("Status do Curso", ["Cursando", "Trancado", "Concluído"])

            st.markdown("#### Áreas de Interesse")
            interesses_selecionados = []
            areas_predefinidas = [
                "Programação", "Robótica", "Inteligência Artificial", "Banco de Dados",
                "Desenvolvimento Web", "Redes de Computadores", "Manutenção de Computador",
                "Segurança da Informação", "Design Gráfico", "Análise de Dados",
                "Automação", "IoT (Internet das Coisas)", "Engenharia de Software",
                "Computação em Nuvem", "Eletrônica Digital"
            ]
            cols = st.columns(3)
            for i, area in enumerate(areas_predefinidas):
                if cols[i % 3].checkbox(area):
                    interesses_selecionados.append(area)

            interesses = ", ".join(interesses_selecionados)

            col4, col5, col6 = st.columns(3)
            with col4:
                rank_gp = st.selectbox("Rank GP", ["E", "D", "C", "B", "A", "S"])
            with col5:
                tipo_membro = st.selectbox("Tipo de Membro", ["Discente", "Professor"]) 
            with col6:
                status = st.selectbox("Status", ["Ativo", "Inativo", "Pendente"])

            enviar = st.form_submit_button("Salvar Membro")
            if enviar:
                novo_membro_raw = {
                    "NOME": nome,
                    "CPF": cpf,
                    "EMAIL": email,
                    "CONTATO": contato,
                    "DATA NASCIMENTO": nascimento,
                    "EQUIPE DE PROJETO": equipe,
                    "PROJETO ATUAL": projeto_atual,
                    "ORIENTADOR": orientador,
                    "CURSO": curso,
                    "LATTES": lattes,
                    "MATRÍCULA": matricula,
                    "TAMANHO CAMISETA": camiseta,
                    "NÍVEL ESCOLARIDADE": escolaridade,
                    "STATUS CURSO": status_curso,
                    "ÁREAS DE INTERESSE": interesses,
                    "TIPO MEMBRO": tipo_membro,
                    "Rank GP": rank_gp,
                    "STATUS": status,
                }
                payload, erros = _validar_e_preparar_membro(
                    novo_membro_raw,
                    cpfs_existentes=cpfs_existentes,
                    emails_existentes=emails_existentes,
                )
                if erros:
                    for err in erros:
                        st.error(err)
                    return
                try:
                    salvar_membro_firestore(payload)
                    st.session_state["toast_membros"] = {"text": "Membro cadastrado!", "icon": "✅"}
                    st.success("✅ Membro salvo com sucesso no Firebase!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao salvar no Firebase: {e}")

    modal()

def aplicar_filtros(df, q_external: str | None = None):
    if df.empty:
        return df

    sb = st.sidebar
    sb.markdown("### 🔎 Filtros — Membros")
    # Busca principal pode vir de fora (topo da página)
    if q_external is None:
        q = sb.text_input("Buscar por nome, CPF, email, orientador, equipe", key="filtro_q")
    else:
        q = q_external
    status_sel = sb.selectbox("Status", ["Todos", "Ativo", "Inativo", "Pendente"], index=0, key="filtro_status")
    
    # Filtro: Ano (valores únicos, ordenados numericamente)
    anos_col = df.get("ANO", pd.Series())
    if not anos_col.empty:
        anos_numeric = pd.to_numeric(anos_col, errors="coerce").dropna().astype(int)
        anos_unique_sorted = sorted(pd.Series(anos_numeric).unique().tolist())
        anos_opts_sorted = [str(a) for a in anos_unique_sorted]
        # Fallback textual se não houver anos numéricos
        if not anos_opts_sorted:
            anos_opts_sorted = sorted(
                pd.Series(anos_col.astype(str).map(str.strip))
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
    else:
        anos_opts_sorted = []
    anos = sb.multiselect("Ano", anos_opts_sorted, key="filtro_anos")
    
    ranks = sb.multiselect(
        "Rank GP",
        sorted(df.get("Rank GP", pd.Series()).dropna().unique().tolist()),
        key="filtro_ranks",
    )
    equipes = sb.multiselect(
        "Equipe",
        sorted(df.get("EQUIPE DE PROJETO", pd.Series()).dropna().unique().tolist()),
        key="filtro_equipes",
    )
    tipos = sb.multiselect(
        "Tipo Membro",
        sorted(df.get("TIPO MEMBRO", pd.Series()).dropna().unique().tolist()),
        key="filtro_tipos",
    )
    orientadores = sb.multiselect(
        "Orientador",
        sorted(df.get("ORIENTADOR", pd.Series()).dropna().unique().tolist()),
        key="filtro_orientadores",
    )
    cursos = sb.multiselect(
        "Curso",
        sorted(df.get("CURSO", pd.Series()).dropna().unique().tolist()),
        key="filtro_cursos",
    )
    projetos = sb.multiselect(
        "Projeto Atual",
        sorted(df.get("PROJETO ATUAL", pd.Series()).dropna().unique().tolist()),
        key="filtro_projetos",
    )


    # Removido filtro de Série conforme solicitado

    col_btn1, col_btn2 = sb.columns(2)
    if col_btn1.button("Limpar filtros"):
        st.session_state["filtro_q"] = ""
        st.session_state["filtro_status"] = "Todos"
        st.session_state["filtro_ranks"] = []
        st.session_state["filtro_equipes"] = []
        st.session_state["filtro_tipos"] = []
        st.session_state["filtro_orientadores"] = []
        st.session_state["filtro_cursos"] = []
        st.session_state["filtro_projetos"] = []
        st.session_state["filtro_anos"] = []
        st.rerun()

    df_filtrado = df.copy()
    if q:
        nq = normalize_string(q)
        def match_row(row):
            campos = [
                row.get("NOME", ""),
                row.get("CPF", ""),
                row.get("EMAIL", ""),
                row.get("ORIENTADOR", ""),
                row.get("EQUIPE DE PROJETO", ""),
                row.get("PROJETO ATUAL", ""),
            ]
            return any(nq in normalize_string(v) for v in campos)
        df_filtrado = df_filtrado[df_filtrado.apply(match_row, axis=1)]
    if status_sel != "Todos" and "STATUS" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["STATUS"] == status_sel]
    if anos:
        df_filtrado = df_filtrado[df_filtrado.get("ANO").astype(str).isin([str(a) for a in anos])]
    if ranks:
        df_filtrado = df_filtrado[df_filtrado.get("Rank GP").isin(ranks)]
    if equipes:
        df_filtrado = df_filtrado[df_filtrado.get("EQUIPE DE PROJETO").isin(equipes)]
    if tipos:
        df_filtrado = df_filtrado[df_filtrado.get("TIPO MEMBRO").isin(tipos)]
    if orientadores:
        df_filtrado = df_filtrado[df_filtrado.get("ORIENTADOR").isin(orientadores)]
    if cursos:
        df_filtrado = df_filtrado[df_filtrado.get("CURSO").isin(cursos)]
    if projetos:
        df_filtrado = df_filtrado[df_filtrado.get("PROJETO ATUAL").isin(projetos)]
    return df_filtrado

def graficos(df):
    if df.empty:
        return
    with st.expander("📈 Ver gráficos"): 
        c1, c2 = st.columns(2)
        if "STATUS" in df.columns:
            fig1 = px.pie(df, names="STATUS", title="Distribuição por Status", hole=0.35)
            c1.plotly_chart(fig1, use_container_width=True)
        if "Rank GP" in df.columns:
            fig2 = px.bar(df.groupby("Rank GP").size().reset_index(name="Qtd"), x="Rank GP", y="Qtd", title="Membros por Rank GP")
            c2.plotly_chart(fig2, use_container_width=True)

        c3, c4 = st.columns(2)
        if "CURSO" in df.columns:
            top_cursos = df["CURSO"].value_counts().head(10).reset_index()
            top_cursos.columns = ["CURSO", "Qtd"]
            fig3 = px.bar(top_cursos, x="CURSO", y="Qtd", title="Top Cursos")
            c3.plotly_chart(fig3, use_container_width=True)
        if "EQUIPE DE PROJETO" in df.columns:
            top_eq = df["EQUIPE DE PROJETO"].value_counts().head(10).reset_index()
            top_eq.columns = ["EQUIPE", "Qtd"]
            fig4 = px.bar(top_eq, x="EQUIPE", y="Qtd", title="Membros por Equipe")
            c4.plotly_chart(fig4, use_container_width=True)

def gestao_membros():
    st.markdown("# Gestão de Membros do GP Mecatrônica")
    _toast_once("toast_membros")

    # Garante CSS do diálogo carregado antes de abrir o modal
    _inject_dialog_css()

    # Barra de ações
    a1, a2, a3, _ = st.columns([1,1,1,4])
    if a1.button("➕ Cadastrar novo membro"):
        cadastrar_membro()
    if a2.button("🔄 Recarregar dados"):
        try:
            st.cache_data.clear()
        finally:
            st.rerun()

    # Carregar dados (Firestore preferencialmente)
    df = carregar_membros_df()
    if df.empty:
        st.error("Não há dados disponíveis (Firestore/CSV).")
        return

    gerenciar_opcoes_textuais(df)

    if "DATA NASCIMENTO" in df.columns:
        df = df.copy()
        data_col = pd.to_datetime(df["DATA NASCIMENTO"], errors="coerce", dayfirst=True)
        df["DATA NASCIMENTO"] = data_col.dt.strftime("%d/%m/%Y").fillna("")

    mostrar_indicadores(df)

    # Busca principal abaixo dos indicadores, acima das abas
    busca_top = st.text_input("Buscar por nome, CPF, email, orientador, equipe", key="busca_top")

    # Filtros (sidebar) com busca vinda do topo
    df = aplicar_filtros(df, q_external=busca_top)

    # Abas por status (com edição apenas em "Todos")
    abas = st.tabs(["Todos", "Ativo", "Inativo", "Pendente"])
    status_map = {"Todos": None, "Ativo": "Ativo", "Inativo": "Inativo", "Pendente": "Pendente"}

    edited_df_master = None
    for i, nome_tab in enumerate(status_map.keys()):
        with abas[i]:
            df_tab = df
            status = status_map[nome_tab]
            if status and "STATUS" in df_tab.columns:
                df_tab = df_tab[df_tab["STATUS"] == status]

            colunas_visiveis = [
                "NOME", "CPF", "DATA NASCIMENTO", "EMAIL", "CONTATO",
                "LATTES", "MATRÍCULA", "EQUIPE DE PROJETO",
                "PROJETO ATUAL", "ORIENTADOR", "SÉRIE", "ANO", "Rank GP",
                "STATUS"
            ]
            colunas_visiveis = [c for c in colunas_visiveis if c in df_tab.columns]
            df_tab = df_tab[colunas_visiveis]

            # Paginação
            total_rows = len(df_tab)
            ps_key = f"ps_{nome_tab}"
            pn_key = f"pn_{nome_tab}"
            page_size = st.session_state.get(ps_key, 25)
            total_pages = max(1, ceil(max(1, total_rows) / page_size))
            page_num = st.session_state.get(pn_key, 1)
            if page_num > total_pages:
                st.session_state[pn_key] = total_pages
                st.rerun()
            start = (page_num - 1) * page_size
            end = start + page_size
            df_page = df_tab.iloc[start:end]
            # Sinalizar linhas atualizadas recentemente (persistidas) nesta página
            updated_key = f"last_updated_{nome_tab}_p{page_num}"
            last_updated_cpfs = set(st.session_state.get(updated_key, []))
            df_page_display = df_page.copy()
            editavel = (nome_tab == "Todos")
            if editavel:
                df_page_display["EXCLUIR"] = False
                # garante coluna no fim
                base_cols = [c for c in df_page_display.columns if c != "EXCLUIR"]
                df_page_display = df_page_display[base_cols + ["EXCLUIR"]]
            if "CPF" in df_page_display.columns:
                df_page_display["ATUALIZADO"] = df_page_display["CPF"].apply(
                    lambda c: "✅" if c in last_updated_cpfs else ""
                )
                # Garante coluna no final
                colunas_visiveis_with_status = colunas_visiveis.copy()
                if editavel and "EXCLUIR" not in colunas_visiveis_with_status:
                    colunas_visiveis_with_status.append("EXCLUIR")
                if "ATUALIZADO" not in colunas_visiveis_with_status:
                    colunas_visiveis_with_status.append("ATUALIZADO")
                df_page_display = df_page_display[colunas_visiveis_with_status]
            else:
                df_page_display = df_page
            first_row = start + 1 if total_rows else 0
            last_row = min(end, total_rows)

            retorno = st.data_editor(
                df_page_display,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "EXCLUIR": st.column_config.CheckboxColumn("Excluir", help="Marque para remover este membro"),
                    "NOME": st.column_config.TextColumn("Nome Completo", disabled=not editavel),
                    "CPF": st.column_config.TextColumn("CPF", disabled=True),
                    "DATA NASCIMENTO": st.column_config.TextColumn("Data Nasc.", disabled=not editavel),
                    "EMAIL": st.column_config.TextColumn("Email", disabled=not editavel),
                    "CONTATO": st.column_config.TextColumn("Telefone", disabled=not editavel),
                    "LATTES": st.column_config.LinkColumn("Currículo Lattes"),
                    "MATRÍCULA": st.column_config.TextColumn("Matrícula", disabled=not editavel),
                    "EQUIPE DE PROJETO": st.column_config.TextColumn("Equipe", disabled=not editavel),
                    "PROJETO ATUAL": st.column_config.TextColumn("Projeto Atual", disabled=not editavel),
                    "ORIENTADOR": st.column_config.TextColumn("Orientador", disabled=not editavel),
                    "SÉRIE": st.column_config.TextColumn("Série", disabled=not editavel),
                    "ANO": st.column_config.TextColumn("Ano", disabled=not editavel),
                    "Rank GP": st.column_config.TextColumn("Rank GP", disabled=not editavel),
                    "STATUS": st.column_config.SelectboxColumn("Status", options=["Ativo", "Inativo", "Pendente"], disabled=not editavel),
                    "ATUALIZADO": st.column_config.TextColumn("Atualizado", disabled=True, help="Última edição persistida"),
                },
                key=f"editor_{nome_tab}_p{page_num}"
            )
            if editavel:
                edited_df_master = retorno
                # Alternar entre autosave e salvar em lote
                autosave_key = f"autosave_{nome_tab}"
                if autosave_key not in st.session_state:
                    st.session_state[autosave_key] = True
                autosave = st.checkbox("Salvar automaticamente", key=autosave_key)

                try:
                    # Remover colunas de UI do retorno para comparar
                    retorno_clean = retorno.drop(columns=[c for c in ["DETALHES", "ATUALIZADO", "EXCLUIR"] if c in retorno.columns])
                    orig_clean = df_page.drop(columns=[c for c in ["DETALHES", "ATUALIZADO", "EXCLUIR"] if c in df_page.columns], errors='ignore')
                    if "CPF" in retorno_clean.columns and "CPF" in orig_clean.columns:
                        retorno_idx = retorno_clean.set_index("CPF")
                        orig_idx = orig_clean.set_index("CPF")
                        campos_editaveis = [
                            c for c in [
                                "NOME","EMAIL","CONTATO","LATTES","MATRÍCULA",
                                "EQUIPE DE PROJETO","ORIENTADOR","SÉRIE","ANO",
                                "Rank GP","STATUS"
                            ] if c in retorno_idx.columns
                        ]
                        changed_cpfs = []
                        for cpf, row in retorno_idx.iterrows():
                            if cpf not in orig_idx.index:
                                continue
                            before = orig_idx.loc[cpf]
                            changed = any(str(row.get(col, "")) != str(before.get(col, "")) for col in campos_editaveis)
                            if changed:
                                changed_cpfs.append(cpf)

                        pending_key = f"pending_{nome_tab}_p{page_num}"
                        st.session_state[pending_key] = changed_cpfs

                        if autosave and changed_cpfs:
                            saved = 0
                            for cpf in changed_cpfs:
                                row = retorno_idx.loc[cpf]
                                payload = row.to_dict()
                                try:
                                    salvar_membro_firestore({**payload, "CPF": cpf})
                                    saved += 1
                                except Exception as e:
                                    st.warning(f"Falha ao salvar CPF {cpf}: {e}")
                            if saved:
                                st.session_state[updated_key] = changed_cpfs
                                st.toast(f"{saved} registro(s) atualizado(s) no Firebase", icon="✅")
                                try:
                                    st.cache_data.clear()
                                except Exception:
                                    pass
                        elif not autosave:
                            # Modo lote: botão aciona um rerun com flag para salvar na próxima execução
                            n_pending = len(changed_cpfs)
                            do_batch_key = f"do_batch_{nome_tab}_p{page_num}"
                            c_b1, _ = st.columns([2,5])
                            if c_b1.button(
                                f"💾 Salvar alterações desta página ({n_pending})",
                                disabled=(n_pending == 0),
                                key=f"batchsave_{nome_tab}_p{page_num}",
                            ):
                                st.session_state[do_batch_key] = True
                                st.rerun()

                            # Se a flag estiver marcada nesta execução, salva usando os diffs atuais
                            if st.session_state.get(do_batch_key, False):
                                saved = 0
                                for cpf in changed_cpfs:
                                    row = retorno_idx.loc[cpf]
                                    payload = row.to_dict()
                                    try:
                                        salvar_membro_firestore({**payload, "CPF": cpf})
                                        saved += 1
                                    except Exception as e:
                                        st.warning(f"Falha ao salvar CPF {cpf}: {e}")
                                st.session_state[updated_key] = changed_cpfs
                                st.session_state[pending_key] = []
                                st.session_state[do_batch_key] = False
                                if saved:
                                    st.toast(f"{saved} registro(s) atualizado(s) no Firebase", icon="✅")
                                    try:
                                        st.cache_data.clear()
                                    except Exception:
                                        pass
                except Exception as e:
                    st.warning(f"Não foi possível verificar alterações: {e}")

                cpfs_excluir = []
                if "EXCLUIR" in retorno.columns and "CPF" in retorno.columns:
                    cpfs_excluir = retorno[retorno["EXCLUIR"] == True]["CPF"].astype(str).tolist()
                if cpfs_excluir:
                    st.warning(f"{len(cpfs_excluir)} membro(s) marcados para exclusão")
                if st.button(
                    f"🗑️ Excluir selecionados ({len(cpfs_excluir)})",
                    disabled=len(cpfs_excluir) == 0,
                    key=f"delete_members_{nome_tab}_p{page_num}",
                    type="secondary",
                ):
                    removidos = deletar_membros(cpfs_excluir)
                    st.toast(f"{removidos} membro(s) removido(s)", icon="✅")
                    try:
                        st.cache_data.clear()
                    finally:
                        st.rerun()

            # Controles de navegação e info abaixo da tabela
            b_prev, b_next, b_info = st.columns([1,1,6])
            prev_disabled = page_num <= 1
            next_disabled = page_num >= total_pages
            if b_prev.button("◀️ Anterior", disabled=prev_disabled, key=f"prev_bottom_{nome_tab}"):
                st.session_state[pn_key] = max(1, page_num - 1)
                st.rerun()
            if b_next.button("Próxima ▶️", disabled=next_disabled, key=f"next_bottom_{nome_tab}"):
                st.session_state[pn_key] = min(total_pages, page_num + 1)
                st.rerun()
            b_info.caption(f"Página {page_num}/{total_pages} • Mostrando {first_row}–{last_row} de {total_rows}")

            # Itens por página abaixo da tabela
            c_ps = st.columns([1])[0]
            with c_ps:
                st.caption("Itens por página")
                novo_ps = st.selectbox(
                    "",
                    options=[10, 25, 50, 100],
                    index={10:0,25:1,50:2,100:3}.get(page_size, 1),
                    key=f"{ps_key}_below",
                    label_visibility="collapsed",
                )
            if novo_ps != page_size:
                st.session_state[ps_key] = novo_ps
                st.rerun()

    # Persistir alterações do editor principal
    if edited_df_master is not None:
        csave1, _ = st.columns([1,5])
        if csave1.button("📤 Salvar alterações no Firebase"):
            try:
                salvar_dataframe_completo(edited_df_master)
                st.success("✅ Alterações salvas no Firebase!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Falha ao salvar no Firebase: {e}")

    # Gráficos
    graficos(df)

    st.markdown("---")
    st.caption(f"📌 Desenvolvido por: Equipe Vingadores — GP Mecatrônica - IFRO Calama • {date.today().year}")
