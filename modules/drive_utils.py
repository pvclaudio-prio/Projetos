import streamlit as st
from datetime import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from oauth2client.client import OAuth2Credentials
import httplib2

@st.cache_resource
def conectar_drive():
    cred = st.secrets.get("credentials", None)
    if not cred:
        st.error("Credenciais do Google não encontradas em st.secrets['credentials'].")
        st.stop()

    # 1) Monta credenciais OAuth2 a partir do secrets
    credentials = OAuth2Credentials(
        access_token=cred.get("access_token"),
        client_id=cred["client_id"],
        client_secret=cred["client_secret"],
        refresh_token=cred["refresh_token"],
        token_expiry=datetime.strptime(cred["token_expiry"], "%Y-%m-%dT%H:%M:%SZ"),
        token_uri=cred["token_uri"],
        user_agent="streamlit-app/1.0",
        revoke_uri=cred["revoke_uri"],
    )

    # 2) Atualiza o token (se expirado)
    http = httplib2.Http()
    try:
        credentials.refresh(http)
    except Exception as e:
        st.error(f"Falha ao atualizar token do Google: {e}")
        st.stop()

    # 3) Injeta um client_config em memória para o PyDrive não buscar client_secrets.json
    gauth = GoogleAuth()
    gauth.settings['client_config_backend'] = 'settings'
    gauth.settings['client_config'] = {
        "client_id": cred["client_id"],
        "client_secret": cred["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": cred["token_uri"],
        "revoke_uri": cred["revoke_uri"],
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
    }
    # 4) Define as credenciais direto no gauth (impede LocalWebserverAuth)
    gauth.credentials = credentials

    # 5) Cria o client do Drive
    drive = GoogleDrive(gauth)
    return drive
