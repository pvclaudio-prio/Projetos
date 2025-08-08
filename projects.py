import streamlit as st
from datetime import date
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.client import OAuth2Credentials
import httplib2
import pandas as pd
import uuid
from modules.drive_utils import conectar_drive
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel
import tempfile
from modules.projetos_atividades import aba_projetos_atividades
import openpyxl

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

# 🔐 Login
usuario_logado, nome_usuario = login()

# 🎨 Sidebar
st.sidebar.markdown(f"👤 Logado como: **{nome_usuario}**")

menu = st.sidebar.radio("📋 Navegação", [
    "🏠 Dashboard",
    "🗂️ Projetos e Atividades",
    "📆 Agenda",
    "💡 Ideias",
    "⚠️ Riscos",
    "💰 Ganhos",
    "📚 Lições Aprendidas",
    "🔎 Visualização Unificada",
    "🤖 IA Consultor"
])

# 📦 Roteamento de páginas
if menu == "🏠 Dashboard":
    st.title("📊 Dashboard de Projetos (Em construção)")

elif menu == "🗂️ Projetos e Atividades":
    aba_projetos_atividades(usuario_logado, nome_usuario)

elif menu == "📆 Agenda":
    st.title("📆 Agenda (Em construção)")

elif menu == "💡 Ideias":
    st.title("💡 Cadastro de Ideias (Em construção)")

elif menu == "⚠️ Riscos":
    st.title("⚠️ Cadastro de Riscos (Em construção)")

elif menu == "💰 Ganhos":
    st.title("💰 Cadastro de Ganhos (Em construção)")

elif menu == "📚 Lições Aprendidas":
    st.title("📚 Lições Aprendidas (Em construção)")

elif menu == "🔎 Visualização Unificada":
    st.title("🔎 Visualização Unificada (Em construção)")

elif menu == "🤖 IA Consultor":
    st.title("🤖 IA Consultor de Projetos (Em construção)")
