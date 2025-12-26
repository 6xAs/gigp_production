import streamlit as st
import pandas as pd
import random

#carregamento de dados
if "df" not in st.session_state:
    st.session_state.df = df = pd.read_csv('database/membros_gp_fakes.csv', sep = ',')
atividade_equipes = (st.session_state.df.groupby("EQUIPE DE PROJETO")["STATUS"].apply(lambda x: (x == "Ativo").sum()).reset_index(name="membros_ativos"))

#configuração da página
st.set_page_config(
    page_title= "Gestão de Equipes",
    page_icon= "🏷️",
    layout= "wide")

#configuração sidebar
st.sidebar.title("NAVEGAÇÃO")
aba = st.sidebar.radio("Ir para:", ["👁️‍🗨️ Visão Geral","👤 Visualizar Membros", "➕ Adicionar Novo", "🗃️ Gerenciar Registros"])

#visão geral
if aba == "👁️‍🗨️ Visão Geral":
    st.header("🖇️ Visão geral")
    st.divider()
    #cards de atividade
    ativos = st.session_state.df[st.session_state.df["STATUS"] == "Ativo"].shape[0]
    inativos = st.session_state.df[st.session_state.df["STATUS"] == "Inativo"].shape[0]
    qtd_equipes = st.session_state.df["EQUIPE DE PROJETO"].nunique()
    col1, col2, col3 = st.columns(3)
    card_style = """
    background-color:#262730;
    width:145px;
    height:145px;
    display:flex;
    align-items:center;
    justify-content:center;
    border: 3px solid #22232B;
    border-radius:20px;
    box-shadow: 0 0 10px rgba(0,0,0,0.2);
    position:relative;
    color:white;
    font-weight:bold;
    font-size:64px;
    margin:auto;"""
    with col1:
        st.markdown(f"""<div style="{card_style}"> {ativos}
        <div style="position:absolute; bottom:12px; right:12px; width:19px; height:19px; border-radius:50%; background-color:#28a745;"></div>
    </div>
    <p style="text-align:center; color:#28a745; font-weight:bold; margin-top:8px;">Membros ativos</p>
    """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div style="{card_style}"> {inativos}
        <div style="position:absolute; bottom:12px; right:12px; width:19px; height:19px; border-radius:50%; background-color:#DC2F36;"></div>
    </div>
    <p style="text-align:center; color:#DC2F36; font-weight:bold; margin-top:8px;">Membros inativos</p>
    """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""<div style="{card_style}"> {qtd_equipes}
    </div>
    <p style="text-align:center; color:#707070; font-weight:bold; margin-top:8px;">Equipes</p>
    """, unsafe_allow_html=True)
    st.divider()
    #cards equipes
    st.subheader("Resumo por Equipe")
    df = st.session_state.df.copy()
    df["STATUS_NORMALIZADO"] = df["STATUS"].astype(str).str.lower().str.strip()
    df["EQUIPE DE PROJETO"] = df["EQUIPE DE PROJETO"].astype(str).str.strip()
    resumo_equipes = df.groupby("EQUIPE DE PROJETO")["STATUS_NORMALIZADO"].value_counts().unstack().fillna(0)
    cards_equipe = ""
    for equipe, row in resumo_equipes.iterrows():
        ativos = int(row.get("ativo", 0))
        inativos = int(row.get("inativo", 0))
        cards_equipe += f"""<div class="card">
        <div style="font-size: 1.25rem; font-weight: bold; text-align: center; margin-bottom: 0.5rem;">{equipe}</div>
        <p class="ativo">{ativos} ativo(s)</p>
        <p class="inativo">{inativos} inativo(s)</p>
    </div>"""
    st.markdown("""
<style>
.scroll-container {
    display: flex;
    overflow-x: auto;
    padding: 1rem 0;
    gap: 1rem;}
.card {
    background-color: #262730;
    color: white;
    padding: 1rem;
    border: 3px solid #22232B;
    border-radius: 12px;
    min-width: 220px;
    flex-shrink: 0;
    box-shadow: 0 0 10px rgba(0,0,0,0.2);
    text-align: center;
    font-family: "Segoe UI", sans-serif;}
.card h4 {
    margin-bottom: 0.5rem;}
.card .ativo {
    color: #28a745;
    font-weight: bold;
    margin: 4px 0 2px 0;
    text-align: center;}
.card .inativo {
    color: #DC2F36;
    font-weight: bold;
    margin: 2px 0 0 0;
    text-align: center;}
</style>""", unsafe_allow_html=True)
    st.markdown(f"""
<div class="scroll-container">
    {cards_equipe}
</div>""", unsafe_allow_html=True)
    #filtro orientadores
    st.subheader("Orientadores")
    orientadores = sorted(st.session_state.df["ORIENTADOR"].dropna().unique())
    options_orientadores = ["Todos"] + orientadores
    orientador_select = st.selectbox("Selecionar orientador:", options_orientadores)
    st.divider()
    def render_orientador_card(nome, orientandos):
        st.markdown(f"""
            <div style="
            background-color: #262730;
            padding: 16px;
            border: 3px solid #22232B;
            border-radius: 12px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
            <h4 style="
                margin: 0 0 8px 0;
                text-align: left;
                font-weight: bold;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: white;">
                👨‍🏫 {nome} | {len(orientandos)} orientandos</h4>
            <details>
                <summary style="cursor: pointer; font-weight: 500; color: #28a745;">Visualizar orientandos</summary>
                <ul style="margin-top: 8px;">
                    {''.join(f"<li>{row['NOME']}</li>" for _, row in orientandos.iterrows())}
                </ul>
            </details>
        </div>""", unsafe_allow_html=True)
    if orientador_select == "Todos":
        for orientador in orientadores:
            df_orientador = st.session_state.df[st.session_state.df["ORIENTADOR"] == orientador]
            render_orientador_card(orientador, df_orientador)
    else:
        df_orientador = st.session_state.df[st.session_state.df["ORIENTADOR"] == orientador_select]
        render_orientador_card(orientador_select, df_orientador)
            
#visualizar membros
elif aba == "👤 Visualizar Membros":
    st.subheader("Lista de Membros")
    equipes = sorted(st.session_state.df["EQUIPE DE PROJETO"].dropna().unique())
    equipe_select = st.selectbox("Filtrar por Equipe:", ["Todas"] + equipes)
    #busca escrita
    busca = st.text_input("Buscar por nome/CPF/matrícula:").strip()
    df_filtrado = st.session_state.df.copy()
    if equipe_select != "Todas":
        df_filtrado = df_filtrado[df_filtrado["EQUIPE DE PROJETO"].str.contains(equipe_select, na=False)]
    if busca:
        colunas_busca = ["NOME", "CPF", "MATRÍCULA"]
        busca_normal = busca.lower()
        mask = df_filtrado[colunas_busca].apply(
        lambda col: col.astype(str).str.lower().str.contains(busca_normal, na=False)).any(axis=1)
        df_filtrado = df_filtrado[mask]
    st.divider()
    #exibir cards
    st.subheader(f"Resultados encontrados: {len(df_filtrado)}")
    for _, membro in df_filtrado.iterrows():
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                estilo_avatar = "pixel-art"
                cores = ["b6e3f4", "c0aede", "d1d4f9", "ffd5dc", "ffdfbf"]
                cor_fundo = random.choice(cores)
                identificador = membro["MATRÍCULA"]
                url_avatar = f"https://api.dicebear.com/7.x/{estilo_avatar}/svg?seed={identificador}&backgroundColor={cor_fundo}"
                st.image(url_avatar, width=192)
            with col2:
                status_key = f"status_{membro['MATRÍCULA']}"
                status_ativo = st.toggle("Ativo", value=(membro["STATUS"].strip().lower() == "ativo"), key=status_key)
                cor_status = "limegreen" if status_ativo else "tomato"
                texto_status = "Ativo" if status_ativo else "Inativo"
                detalhes = f"detalhes_{membro['MATRÍCULA']}"
                st.markdown(f"""
                <div style="background-color:#262730;padding:20px;border-radius:12px">
                    <h3 style="margin-bottom:5px;">{membro["NOME"]}</h3>
                    <p><strong>Curso:</strong> {membro["CURSO"]} &nbsp;|&nbsp;
                    <strong>Equipe:</strong> {membro["EQUIPE DE PROJETO"].replace(";", ", ")} &nbsp;|&nbsp;
                    <strong>Status:</strong> <span style="color:{cor_status}; font-weight:bold">{texto_status}</span></p>
                    <details style="margin-top:10px;">
                    <summary style="cursor: pointer; font-weight: 500; color: white;">Mais detalhes</summary>
                    <div style="margin-top:8px; font-size:0.95rem;">
                    <hr style="margin:10px 0;"> <p>
                    <strong>Email:</strong> {membro["EMAIL"]}<br>
                    <strong>Contato:</strong> {membro["CONTATO"]}<br>
                    <strong>CPF:</strong> {membro["CPF"]}<br>
                    <strong>Lattes:</strong> {membro["LATTES"]}<br>
                    <strong>Nascimento:</strong> {membro["DATA NASCIMENTO"]}<br>
                    <strong>Matrícula:</strong> {membro["MATRÍCULA"]}<br>
                    <strong>Série:</strong> {membro["SÉRIE"]} &nbsp;|&nbsp;
                    <strong>Tam. Camiseta:</strong> {membro["TAMANHO CAMISETA"]}<br>
                    <strong>Escolaridade:</strong> {membro["NÍVEL ESCOLARIDADE"]}<br>
                    <strong>Status Curso:</strong> {membro["STATUS CURSO"]}<br>
                    <strong>Tipo:</strong> {membro["TIPO MEMBRO"]}<br>
                    <strong>Rank GP:</strong> {membro["RANK GP"]}<br>
                    <strong>Orientador:</strong> {membro["ORIENTADOR"]}
                    </p>
                   </div>
            </details>
        </div>""", unsafe_allow_html=True)
        st.divider()

#adicionar novo
elif aba == "➕ Adicionar Novo":
    st.title("Adicionar novo")
    options = st.radio("O que deseja adicionar?", ["Membro", "Equipe"], horizontal=True)
    if options == "Membro":
        with st.form("form_membro"):
            st.subheader("Novo Membro")
            nome = st.text_input("Nome completo")
            id = st.text_input("ID")
            cpf = st.text_input("CPF")
            email = st.text_input("Email")
            contato = st.text_input("Telefone de contato")
            lattes = st.text_input("Lattes")
            matricula = st.text_input("Matrícula")
            tamanho_camiseta = st.selectbox("Tamanho da camiseta", ["PP", "P", "M", "G", "GG", "XGG"])
            data_nascimento = st.date_input("Data de nascimento")
            equipe_projeto = st.multiselect("Equipes do projeto", options=sorted(st.session_state.df["EQUIPE DE PROJETO"].dropna().unique()))
            orientador = st.text_input("Orientador")
            serie = st.selectbox("Série", ["1º ano", "2º ano", "3º ano"])
            ano = st.number_input("Ano", min_value=2020, max_value=2030, step=1, value=2025)
            nivel_escolaridade = st.selectbox("Nível de escolaridade", ["Ensino Fundamental", "Ensino Médio", "Ensino Superior", "Pós-Graduação"])
            curso = st.text_input("Curso")
            status_curso = st.selectbox("Status no curso", ["Cursando", "Concluído", "Trancado"])
            areas_interesse = st.text_input("Áreas de interesse (separadas por vírgula)")
            tipo_membro = st.selectbox("Tipo de membro", ["Discente", "Docente", "Técnico"])
            rank_gp = st.selectbox("Rank GP", ["Iniciante", "Intermediário", "Avançado"])
            status = st.selectbox("Status de atividade", ["Ativo", "Inativo"])
            enviado = st.form_submit_button("Adicionar membro")
            if enviado:
                novo_membro = {
                    "ID": id,
                    "NOME": nome,
                    "CPF": cpf,
                    "EMAIL": email,
                    "CONTATO": contato,
                    "LATTES": lattes,
                    "MATRÍCULA": matricula,
                    "TAMANHO CAMISETA": tamanho_camiseta,
                    "DATA NASCIMENTO": data_nascimento.strftime("%Y-%m-%d"),
                    "EQUIPE DE PROJETO": ";".join(equipe_projeto),
                    "ORIENTADOR": orientador,
                    "SÉRIE": serie,
                    "ANO": ano,
                    "NÍVEL ESCOLARIDADE": nivel_escolaridade,
                    "CURSO": curso,
                    "STATUS CURSO": status_curso,
                    "ÁREAS DE INTERESSE": areas_interesse,
                    "TIPO MEMBRO": tipo_membro,
                    "RANK GP": rank_gp,
                    "STATUS": status}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo_membro])], ignore_index=True)
                st.success(f"Membro {nome} adicionado com sucesso!")
    elif options == "Equipe":
        with st.form("form_equipe"):
            st.subheader("Nova Equipe")
            nome_equipe = st.text_input("Nome da equipe")
            descricao = st.text_area("Descrição (opcional)")
            orientador = st.text_input("Orientador responsável")
            status_equipe = st.selectbox("Status da equipe", ["Ativa", "Inativa"])
            enviado_equipe = st.form_submit_button("Adicionar equipe")
            if enviado_equipe:
                if nome_equipe in st.session_state.df["EQUIPE DE PROJETO"].unique():
                    st.warning("Essa equipe já está cadastrada.")
                else:
                    nova_linha = {
                    "ID": "",
                    "NOME": "",
                    "EQUIPE DE PROJETO": nome_equipe,
                    "ORIENTADOR": orientador,
                    "STATUS": status_equipe,
                    "CURSO": "",
                    "EMAIL": "",
                    "CPF": "",
                    "CONTATO": "",
                    "LATTES": "",
                    "MATRÍCULA": "",
                    "tamanho_camiseta": "",
                    "DATA NASCIMENTO": "",
                    "SÉRIE": "",
                    "ANO": "",
                    "NÍVEL ESCOLARIDADE": "",
                    "STATUS CURSO": "",
                    "ÁREAS DE INTERESSE": "",
                    "TIPO MEMBRO": "",
                    "RANK GP": ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([nova_linha])], ignore_index=True)
                st.success(f"Equipe '{nome_equipe}' adicionada com sucesso!")

#gerenciar registros
else:
    st.title("Gerenciamento de equipes")
    atividade_equipes = atividade_equipes.rename(columns={"EQUIPE DE PROJETO": "Equipe", "membros_ativos": "Membros Ativos", "STATUS_EQUIPE": "Status"})
    atividade_equipes["Status"] = atividade_equipes["Membros Ativos"].apply(lambda n: "Ativa" if n >= 2 else "Inativa")
    st.subheader("Status das equipes")
    st.markdown("""
    <style>
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        border-radius: 16px;
        overflow: hidden;
        align-items:center;
        background-color: #262730;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);}
    .custom-table th {
        background-color: #FF4B4B;
        color: white;
        padding: 10px;
        text-align: center;}
    .custom-table td {
        padding: 10px;
        text-align: center;
        border-bottom: 1px solid #ddd;}
    .custom-table tr:hover {
        background-color: #2E303B;}
    .status-ativa {
        color: #28a745;
        font-weight: bold;}
    .status-inativa {
        color: #DC2F36;
        font-weight: bold;}
    </style>""", unsafe_allow_html=True)
    html_table = atividade_equipes.to_html(classes="custom-table", index = False, escape = False)
    html_table = html_table.replace("Ativa", "<span class='status-ativa'>Ativa</span>")
    html_table = html_table.replace("Inativa", "<span class='status-inativa'>Inativa</span>")
    st.markdown(html_table, unsafe_allow_html=True)
    st.title("Remover Registros")
    options_remove = st.radio("O que deseja remover?", ["Membro", "Equipe"])
    if options_remove == "Membro":                          
        nomes = st.session_state.df["NOME"].tolist()
        membro_select = [f"{row["NOME"]} - {row["EQUIPE DE PROJETO"]}" for _, row in st.session_state.df.iterrows()]
        remove_select = st.selectbox("Selecione o membro que deseja remover:", membro_select)
        if st.button("Remover membro", type = "primary"):
            nome_select, equipe_select2 = remove_select.split(" - ")
            df_filtrado = st.session_state.df
            st.session_state.df = df_filtrado[
                ~((df_filtrado["NOME"] == nome_select) & (df_filtrado["EQUIPE DE PROJETO"] == equipe_select2))]
            st.success(f"Membro {nome_select} da equipe {equipe_select2} foi removido com sucesso!")
    else:
        equipes_open = st.session_state.df["EQUIPE DE PROJETO"].unique().tolist()
        equipe_select3 = st.selectbox("Selecione a equipe que deseja remover por inteiro:", equipes_open)
        membros_equipe = st.session_state.df[st.session_state.df["EQUIPE DE PROJETO"] == equipe_select3]
        st.write(f"Essa equipe possui {len(membros_equipe)} membro(s).")
        if st.button("Remover equipe", type = "primary"):
            st.session_state.df = st.session_state.df[st.session_state.df["EQUIPE DE PROJETO"] != equipe_select3]
            st.success(f"Equipe {equipe_select3} e todos os seus membros foram removidos com sucesso!")