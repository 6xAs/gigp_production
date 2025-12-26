import time
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from models.usuario_model import autenticar_usuario
from views.dashboards.view_home_dash import dash_home
from views.membros.view_membros_dash import gestao_membros
from views.membros.view_perfil_membro import view_perfil_membro
from views.projetos.view_projetos_dash import gestao_projetos
from views.equipes.view_equipes_dash import gestao_equipes
from views.patrimonios.view_patrimonio_dash import gestao_patrimonios


def _init_session():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "usuario" not in st.session_state:
        st.session_state.usuario = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "login_future" not in st.session_state:
        st.session_state.login_future = None
    if "login_started_at" not in st.session_state:
        st.session_state.login_started_at = None


@st.cache_resource
def _login_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1)


def _render_login():
    future = st.session_state.login_future
    if future is not None:
        if future.done():
            st.session_state.login_future = None
            st.session_state.login_started_at = None
            try:
                ok, role = future.result()
            except Exception:
                st.error("Falha ao validar o login. Tente novamente.")
                return
            if ok:
                st.session_state.autenticado = True
                st.session_state.role = role
                st.success("Login realizado com sucesso. Bem-vindo(a)!")
                st.rerun()
                return
            st.error("Email ou senha inválidos. Verifique as credenciais e tente novamente.")
        else:
            started = st.session_state.login_started_at or time.time()
            elapsed = time.time() - started
            if elapsed > 8:
                st.session_state.login_future = None
                st.session_state.login_started_at = None
                st.error("Não foi possível validar o login agora. Tente novamente.")
            else:
                if hasattr(st, "autorefresh"):
                    st.autorefresh(interval=1000, key="login_wait")
                st.info("Validando acesso...")
                if st.button("Cancelar", use_container_width=True):
                    st.session_state.login_future = None
                    st.session_state.login_started_at = None
            if st.session_state.login_future is not None:
                return

    col_esq, col_centro, col_dir = st.columns([1, 1, 1])
    with col_centro:
        st.markdown("<h2 style='text-align:center;'>🔐 Login</h2>", unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("Email", placeholder="ex: gestor@empresa.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            entrar = st.form_submit_button("Entrar", use_container_width=True)
            if entrar:
                st.session_state.usuario = usuario.strip()
                st.session_state.login_started_at = time.time()
                st.session_state.login_future = _login_executor().submit(
                    autenticar_usuario,
                    usuario,
                    senha,
                )
                st.rerun()


def _realizar_logout():
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.role = None
    try:
        st.query_params.clear()
    except Exception:
        pass

###################### CONFIGURAÇÃO DA PÁGINA ######################
st.set_page_config(
    page_title="GP MECATRÔNICA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

###################### LOGO ######################
st.logo(
    image="assets/images/logo_gp/gp_ico.png",
    size="large",
    link=None,
    icon_image=None,
)

###################### AUTENTICAÇÃO ######################
_init_session()
if not st.session_state.autenticado:
    _render_login()
    st.stop()

###################### TÍTULO ######################
st.title("📋 Gestão Interna GP MECATRÔNICA")

###################### MENU LATERAL ######################
role_label = f" ({st.session_state.role})" if st.session_state.role else ""
st.sidebar.markdown(f"👋 Olá, **{st.session_state.usuario}**{role_label}")

menu = st.sidebar.selectbox(
    "📋 Navegação",
    options=[
        "🏠 Dashboard",
        "🪪 Gestão de Membros",
        "👩‍💻 Gestão de Projetos",
        "👫 Gestão de Equipes",
        "📦 Gestão de patrimônios",
    ],
    index=0,
)
st.sidebar.markdown("---")

###################### ROTEAMENTO ######################
try:
    if menu == "🏠 Dashboard":
        dash_home()
    elif menu == "🪪 Gestão de Membros":
        if st.query_params.get("pagina") == "perfil_membro":
            view_perfil_membro()
        else:
            gestao_membros()
    elif menu == "👩‍💻 Gestão de Projetos":
        gestao_projetos()
    elif menu == "👫 Gestão de Equipes":
        gestao_equipes()
    elif menu == "📦 Gestão de patrimônios":
        gestao_patrimonios()
except Exception as e:
    st.error(f"Ocorreu um erro ao carregar a página: {e}")

st.sidebar.markdown("---")
logout_clicked = st.sidebar.button("🔚 Encerrar sessão", use_container_width=True)
if logout_clicked:
    _realizar_logout()
    st.rerun()
