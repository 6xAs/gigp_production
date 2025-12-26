import streamlit as st
import pandas as pd
from datetime import date
from controllers.membros_controller import listar_membros_firestore


def _chip(texto: str, color: str = "#4c6fff"):
    return f"""<span style="background:{color};color:#fff;padding:4px 10px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;">{texto}</span>"""


def _avatar(nome: str):
    iniciais = "".join([p[0] for p in nome.split()[:2]]).upper() or "GP"
    return f"""
    <div style="
        width:80px;height:80px;border-radius:50%;
        background:linear-gradient(135deg,#4c6fff,#7dd3fc);
        display:flex;align-items:center;justify-content:center;
        color:#fff;font-size:28px;font-weight:700;
        box-shadow:0 8px 20px rgba(76,111,255,0.25);
    ">{iniciais}</div>
    """


def _info_row(label: str, value: str):
    return f"""
    <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f2f6;">
        <span style="color:#6b7280;font-weight:600;">{label}</span>
        <span style="color:#0f172a;font-weight:600;">{value or '-'} </span>
    </div>
    """


def view_perfil_membro():
    st.markdown(
        """
        <style>
        .card {
            background:#fff;
            border-radius:14px;
            padding:18px;
            box-shadow:0 10px 30px rgba(15,23,42,0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    query_params = st.query_params
    cpf = query_params.get("cpf", None)

    if not cpf:
        st.warning("⚠️ Nenhum CPF fornecido na URL.")
        return

    try:
        df = listar_membros_firestore()
    except Exception as e:
        st.error(f"❌ Erro ao acessar o Firestore: {e}")
        return

    membro = df[df["CPF"] == cpf]

    if membro.empty:
        st.error(f"❌ Nenhum membro encontrado com CPF: {cpf}")
        return

    dados = membro.iloc[0]
    nome = dados.get("NOME", "Membro")
    status = dados.get("STATUS", "Pendente")
    projeto = dados.get("PROJETO ATUAL", "")
    equipe = dados.get("EQUIPE DE PROJETO", "")
    orientador = dados.get("ORIENTADOR", "")
    curso = dados.get("CURSO", "")
    rank = dados.get("Rank GP", "")
    contatos = {"Email": dados.get("EMAIL", ""), "Contato": dados.get("CONTATO", "")}

    campos_chave = ["EMAIL", "CONTATO", "CURSO", "EQUIPE DE PROJETO", "PROJETO ATUAL", "ORIENTADOR", "Rank GP", "STATUS"]
    preenchidos = sum(1 for c in campos_chave if str(dados.get(c, "")).strip())
    progresso = int((preenchidos / len(campos_chave)) * 100) if campos_chave else 0

    st.markdown(f"### 👤 {nome}")

    top1, top2 = st.columns([1, 2])
    with top1:
        st.markdown(
            f"""
            <div class="card" style="text-align:center;">
                {_avatar(nome)}
                <h3 style="margin:10px 0 4px 0;">{nome}</h3>
                <div style="margin-bottom:6px;">{_chip(status, '#10b981')}</div>
                <div style="color:#6b7280;font-size:13px;">Rank GP: <b>{rank or '-'}</b></div>
                <div style="color:#6b7280;font-size:13px;">Curso: <b>{curso or '-'}</b></div>
                <div style="margin-top:10px;font-size:12px;color:#6b7280;">Atualizado: {date.today().strftime('%d/%m/%Y')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with top2:
        st.markdown(
            f"""
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="color:#6b7280;font-weight:600;">Completude do perfil</div>
                        <div style="font-size:24px;font-weight:700;color:#0f172a;">{progresso}%</div>
                    </div>
                    <div style="width:160px;background:#f3f4f6;height:10px;border-radius:20px;overflow:hidden;">
                        <div style="width:{progresso}%;height:100%;background:linear-gradient(90deg,#4c6fff,#22c55e);"></div>
                    </div>
                </div>
                <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;">
                    {_chip('Projeto: ' + (projeto or 'Sem projeto'), '#0ea5e9')}
                    {_chip('Equipe: ' + (equipe or 'Sem equipe'), '#6366f1')}
                    {_chip('Orientador: ' + (orientador or 'Sem orientador'), '#f59e0b')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### Contatos")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown(
            f"""
            <div class="card">
                {_info_row("Email", contatos.get("Email", "-"))}
                {_info_row("Telefone", contatos.get("Contato", "-"))}
                {_info_row("Matrícula", dados.get("MATRÍCULA", "-"))}
                {_info_row("Tamanho Camiseta", dados.get("TAMANHO CAMISETA", "-"))}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_c2:
        st.markdown(
            f"""
            <div class="card">
                {_info_row("Status curso", dados.get("STATUS CURSO", "-"))}
                {_info_row("Nível", dados.get("NÍVEL ESCOLARIDADE", "-"))}
                {_info_row("Data Nascimento", dados.get("DATA NASCIMENTO", "-"))}
                {_info_row("Tipo Membro", dados.get("TIPO MEMBRO", "-"))}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### Áreas de Interesse")
    interesses = [a.strip() for a in str(dados.get("ÁREAS DE INTERESSE", "")).split(",") if a.strip()]
    if not interesses:
        st.info("Nenhuma área de interesse informada.")
    else:
        chips = "".join(_chip(a, "#1d4ed8") for a in interesses)
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{chips}</div>', unsafe_allow_html=True)

    st.markdown("#### Dados completos")
    info_pairs = {
        "CPF": dados.get("CPF", "-"),
        "Projeto(s)": projeto or "-",
        "Equipe(s)": equipe or "-",
        "Orientador(es)": orientador or "-",
        "Curso": curso or "-",
        "Rank GP": rank or "-",
        "Ano": dados.get("ANO", "-"),
        "Série": dados.get("SÉRIE", "-"),
        "Lattes": dados.get("LATTES", "-"),
    }
    df_info = pd.DataFrame(list(info_pairs.items()), columns=["Campo", "Valor"])
    st.dataframe(df_info, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.link_button("🔙 Voltar para lista de membros", url="?")
