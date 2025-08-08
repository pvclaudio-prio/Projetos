import streamlit as st
from datetime import date
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.client import OAuth2Credentials
import httplib2

@st.cache_data
def carregar_usuarios():
    usuarios_config = st.secrets.get("users", {})
    usuarios = {}
    for user, dados in usuarios_config.items():
        try:
            nome, senha = dados.split("|", 1)
            usuarios[user] = {"name": nome, "password": senha}
        except:
            st.warning(f"Erro ao carregar usuário '{user}' nos secrets.")
    return usuarios

def login():
    st.set_page_config(page_title="Gestão de Projetos", layout="wide")
    st.sidebar.image("PRIO_SEM_POLVO_PRIO_PANTONE_LOGOTIPO_Azul.png", use_column_width=True)
    st.sidebar.markdown(f"📅 Hoje é: **{date.today().strftime('%d/%m/%Y')}**")

    users = carregar_usuarios()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    if not st.session_state.logged_in:
        st.title("🔐 Login")
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            user = users.get(username)
            if user and user["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Bem-vindo, {user['name']}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        st.stop()

    nome_usuario = users[st.session_state.username]["name"]
    st.sidebar.success(f"Logado como: {nome_usuario}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    return st.session_state.username, nome_usuario

@st.cache_resource
def conectar_drive():
    cred_dict = st.secrets["credentials"]
    credentials = OAuth2Credentials(
        access_token=cred_dict["access_token"],
        client_id=cred_dict["client_id"],
        client_secret=cred_dict["client_secret"],
        refresh_token=cred_dict["refresh_token"],
        token_expiry=datetime.strptime(cred_dict["token_expiry"], "%Y-%m-%dT%H:%M:%SZ"),
        token_uri=cred_dict["token_uri"],
        user_agent="streamlit-app/1.0",
        revoke_uri=cred_dict["revoke_uri"]
    )

    http = httplib2.Http()

    try:
        credentials.refresh(http)
    except Exception as e:
        st.error(f"Erro ao atualizar credenciais: {e}")
        st.stop()

    gauth = GoogleAuth()
    gauth.credentials = credentials
    drive = GoogleDrive(gauth)
    return drive

# 🔐 Autenticação
usuario_logado, nome_usuario = login()

