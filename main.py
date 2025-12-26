import streamlit as st
from views.dashboards.view_home_dash import dash_home
from views.membros.view_membros_dash import gestao_membros
from views.membros.view_perfil_membro import view_perfil_membro
from views.projetos.view_projetos_dash import gestao_projetos
from views.equipes.view_equipes_dash import gestao_equipes
from views.patrimonios.view_patrimonio_dash import gestao_patrimonios


def _get_authenticated_email() -> str | None:
    user = getattr(st, "experimental_user", None)
    if not user:
        return None
    email = getattr(user, "email", None)
    if email:
        return email
    try:
        return user.get("email")
    except Exception:
        return None


def _authorize_email(email: str | None) -> tuple[bool, str | None]:
    if not email:
        return False, None
    return True, None

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
email = _get_authenticated_email()
autorizado, role = _authorize_email(email)
if not autorizado:
    st.markdown(
        """
        <div style="padding: 1.25rem; border: 1px solid #ffe4b5; border-radius: 12px; background: #fff8e8;">
          <h2 style="margin: 0 0 .5rem 0;">🔒 Login necessário</h2>
          <p style="margin: 0 0 .75rem 0;">
            Não foi possível identificar seu email.
          </p>
          <p style="margin: 0; font-size: .95rem;">
            Confirme se o app está marcado como <strong>Private</strong> no Streamlit Cloud e
            se seu email está na lista de permitidos.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

###################### TÍTULO ######################
st.title("📋 Gestão Interna GP MECATRÔNICA")

###################### MENU LATERAL ######################
role_label = f" ({role})" if role else ""
st.sidebar.markdown(f"👋 Olá, **{email}**{role_label}")

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
