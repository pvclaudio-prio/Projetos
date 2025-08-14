import streamlit as st
from datetime import date

# ──────────────────────────────────────────────────────────────────────────────
# ⚙️ Configurações Globais da Página (deve ser chamado antes de qualquer UI)
st.set_page_config(page_title="Gestão de Projetos", layout="wide")
# ──────────────────────────────────────────────────────────────────────────────

# 📦 Imports dos módulos internos (mantidos conforme seu projeto)
from modules.drive_utils import conectar_drive  # usado nas abas internas
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel  # idem
from modules.projetos_atividades import aba_projetos_atividades
from modules.cadastro_ideias import cadastro_ideias
from modules.cadastro_riscos import cadastro_riscos
from modules.agenda import agenda_semanal
from modules.financeiro_projeto import aba_financeiro_projeto
from modules.pontos_focais import aba_pontos_focais

# Caminho do logo (ajuste se necessário)
LOGO_PATH = "PRIO_SEM_POLVO_PRIO_PANTONE_LOGOTIPO_Azul.png"


@st.cache_data(show_spinner=False)
def carregar_usuarios():
    """Carrega usuários do st.secrets no formato:
    [secrets.toml]
    [users]
    joao = "João da Silva|senha123"
    maria = "Maria Souza|outra_senha"
    """
    usuarios_config = st.secrets.get("users", {})
    usuarios = {}
    if not usuarios_config:
        st.warning("Nenhum usuário encontrado em st.secrets['users'].")
    for user, dados in usuarios_config.items():
        try:
            nome, senha = dados.split("|", 1)
            usuarios[user] = {"name": nome.strip(), "password": senha.strip()}
        except Exception:
            st.warning(f"⚠️ Erro ao carregar credenciais do usuário '{user}' em secrets. Use o formato 'Nome|Senha'.")
    return usuarios


def login():
    """Fluxo simples de autenticação baseado em st.secrets.
    Mantém estado em st.session_state e oferece botão de logout na sidebar.
    """
    # Cabeçalho lateral
    try:
        st.sidebar.image(LOGO_PATH, use_column_width=True)
    except Exception:
        st.sidebar.write("🖼️ **Logo não encontrado** — verifique o caminho: ", LOGO_PATH)
    st.sidebar.markdown(f"📅 Hoje é: **{date.today().strftime('%d/%m/%Y')}**")

    users = carregar_usuarios()

    # Inicialização de estado
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # Tela de login
    if not st.session_state.logged_in:
        st.title("🔐 Login")
        with st.form("form_login", clear_on_submit=False):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")
        if submitted:
            user = users.get(username)
            if user and user["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Bem-vindo, {user['name']}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        st.stop()

    # Pós-login
    nome_usuario = users.get(st.session_state.username, {}).get("name", st.session_state.username)
    st.sidebar.success(f"Logado como: {nome_usuario}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    return st.session_state.username, nome_usuario


# 🔐 Login
usuario_logado, nome_usuario = login()

# 🎨 Sidebar de Navegação
st.sidebar.markdown(f"👤 Logado como: **{nome_usuario}**")
menu = st.sidebar.radio(
    "📋 Navegação",
    [
        "🏠 Dashboard",
        "🗂️ Projetos e Atividades",
        "📆 Agenda",
        "💡 Ideias",
        "⚠️ Riscos",
        "💰 Ganhos",
        "📚 Lições Aprendidas",
        "🔎 Visualização Unificada",
        "💵 Financeiro do Projeto",
        "👥 Pontos Focais",
        "🤖 IA Consultor",
    ],
    index=0,
)

# 📦 Roteamento de páginas
if menu == "🏠 Dashboard":
    try:
        dashboard_principal()
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Dashboard': {e}")

elif menu == "🗂️ Projetos e Atividades":
    # Envolvemos em try/except para evitar que um erro interno derrube o app inteiro
    try:
        aba_projetos_atividades(usuario_logado, nome_usuario)
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Projetos e Atividades': {e}")

elif menu == "📆 Agenda":
    try:
        agenda_semanal()
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Agenda': {e}")

elif menu == "💡 Ideias":
    try:
        cadastro_ideias()
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Ideias': {e}")

elif menu == "⚠️ Riscos":
    try:
        cadastro_riscos()
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Riscos': {e}")

elif menu == "💰 Ganhos":
    st.title("💰 Cadastro de Ganhos (Em construção)")

elif menu == "📚 Lições Aprendidas":
    st.title("📚 Lições Aprendidas (Em construção)")

elif menu == "🔎 Visualização Unificada":
    st.title("🔎 Visualização Unificada (Em construção)")

elif menu == "💵 Financeiro do Projeto":
    try:
        aba_financeiro_projeto(usuario_logado, nome_usuario)
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Financeiro do Projeto': {e}")

elif menu == "👥 Pontos Focais":
    try:
        aba_pontos_focais(usuario_logado, nome_usuario)
    except Exception as e:
        st.error(f"Erro ao abrir a aba 'Pontos Focais': {e}")

elif menu == "🤖 IA Consultor":
    st.title("🤖 IA Consultor de Projetos (Em construção)")
