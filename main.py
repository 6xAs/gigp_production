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
    if "nome_usuario" not in st.session_state:
        st.session_state.nome_usuario = None


def _render_login():
    col_esq, col_centro, col_dir = st.columns([1, 1, 1])
    with col_centro:
        st.markdown("<h2 style='text-align:center;'>🔐 Login</h2>", unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("Email", placeholder="ex: gestor@empresa.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            entrar = st.form_submit_button("Entrar", use_container_width=True)
            if entrar:
                ok, role, nome = autenticar_usuario(usuario, senha)
                if ok:
                    st.session_state.autenticado = True
                    st.session_state.usuario = usuario.strip()
                    st.session_state.nome_usuario = nome
                    st.session_state.role = role
                    st.success("Login realizado com sucesso. Bem-vindo(a)!")
                    st.rerun()
                else:
                    if role == "firestore_indisponivel":
                        st.error(
                            "Não foi possível conectar ao Firestore agora. "
                            "Tente novamente em alguns instantes."
                        )
                    else:
                        st.error(
                            "Email ou senha inválidos. Verifique as credenciais e tente novamente."
                        )


def _realizar_logout():
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.role = None
    st.session_state.nome_usuario = None
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
display_name = st.session_state.nome_usuario or st.session_state.usuario
st.sidebar.markdown(f"👋 Olá, **{display_name}**{role_label}")

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
st.sidebar.markdown(
    """
    <style>
    div[data-testid="stSidebar"] button {
        background: #3CB371;
        color: #ffffff;
        border: 1px solid #3CB371;
    }
    div[data-testid="stSidebar"] button:hover {
        background: #2f9a5e;
        color: #ffffff;
        border: 1px solid #2f9a5e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
logout_clicked = st.sidebar.button("🔚 Encerrar sessão", use_container_width=True)
if logout_clicked:
    _realizar_logout()
    st.rerun()
