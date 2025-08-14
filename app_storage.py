# -*- coding: utf-8 -*-
from __future__ import annotations
import os, io
from typing import Optional
import pandas as pd

# Dependências opcionais do Google Drive (PyDrive + oauth2client)
HAS_GDRIVE = True
try:
    import streamlit as st
    import httplib2
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    from oauth2client.client import OAuth2Credentials
except Exception:
    HAS_GDRIVE = False

# -----------------------------
# Config
# -----------------------------
# Pasta local de fallback (quando não houver Drive)
LOCAL_DIR = os.environ.get("APP_DATA_DIR", "./data_excel")

# Mapa nome_base -> nome_arquivo Excel
FILES = {
    "projetos": "projetos.xlsx",
    "atividades": "atividades.xlsx",
    "financeiro": "financeiro_projeto.xlsx",
    "pontos_focais": "pontos_focais.xlsx",
    "riscos": "riscos.xlsx",
}

# Nome da pasta no Drive onde os xlsx ficam (pode trocar em st.secrets["drive_base_folder"])
DEFAULT_DRIVE_FOLDER_NAME = "GestaoProjetosApp"

# -----------------------------
# Autenticação & utilitários Drive
# -----------------------------
def conectar_drive():
    """Autentica no Google Drive usando o modelo do usuário (st.secrets['credentials'])."""
    if not HAS_GDRIVE:
        return None
    cred_dict = getattr(st, "secrets", {}).get("credentials") if hasattr(st, "secrets") else None
    if not cred_dict:
        return None
    try:
        from datetime import datetime
        credentials = OAuth2Credentials(
            access_token=cred_dict.get("access_token"),
            client_id=cred_dict.get("client_id"),
            client_secret=cred_dict.get("client_secret"),
            refresh_token=cred_dict.get("refresh_token"),
            token_expiry=datetime.strptime(cred_dict.get("token_expiry"), "%Y-%m-%dT%H:%M:%SZ") if cred_dict.get("token_expiry") else None,
            token_uri=cred_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            user_agent=cred_dict.get("user_agent", "streamlit-app/1.0"),
            revoke_uri=cred_dict.get("revoke_uri", "https://oauth2.googleapis.com/revoke"),
        )
        if not credentials.access_token or getattr(credentials, "access_token_expired", False):
            credentials.refresh(httplib2.Http())

        gauth = GoogleAuth()
        # evita erro "Missing required setting client_config"
        gauth.settings["client_config"] = {
            "client_id": cred_dict.get("client_id"),
            "client_secret": cred_dict.get("client_secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "revoke_uri": "https://oauth2.googleapis.com/revoke",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
        gauth.credentials = credentials
        return GoogleDrive(gauth)
    except Exception:
        return None

def obter_id_pasta(nome_pasta: str, parent_id: Optional[str] = None) -> Optional[str]:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        # pydrive (Drive v2) usa "title"
        query = f"title = '{nome_pasta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        resultado = drive.ListFile({'q': query}).GetList()
        if resultado:
            return resultado[0]['id']
        # criar se não existir
        folder = drive.CreateFile({
            'title': nome_pasta,
            'mimeType': 'application/vnd.google-apps.folder'
        })
        if parent_id:
            folder['parents'] = [{'id': parent_id}]
        folder.Upload()
        return folder['id']
    except Exception:
        return None

def _buscar_arquivo(drive, parent_id: str, titulo: str) -> Optional[object]:
    try:
        q = f"'{parent_id}' in parents and title = '{titulo}' and trashed = false"
        lst = drive.ListFile({'q': q}).GetList()
        return lst[0] if lst else None
    except Exception:
        return None

# -----------------------------
# Leitura/Gravação Excel (Drive ou local)
# -----------------------------
def load_base(nome: str) -> pd.DataFrame:
    """Carrega base como Excel do Drive (se disponível) ou do disco local."""
    fname = FILES.get(nome, f"{nome}.xlsx")

    # Tenta Drive primeiro
    drive = conectar_drive()
    if drive:
        base_folder = getattr(st, "secrets", {}).get("drive_base_folder", DEFAULT_DRIVE_FOLDER_NAME)
        folder_id = obter_id_pasta(base_folder)
        if folder_id:
            f = _buscar_arquivo(drive, folder_id, fname)
            if f:
                mem = io.BytesIO()
                f.GetContentFile("tmp.xlsx")  # baixa em arquivo temporário por compatibilidade
                with open("tmp.xlsx", "rb") as fh:
                    mem.write(fh.read())
                mem.seek(0)
                try:
                    return pd.read_excel(mem)
                except Exception:
                    return pd.DataFrame()

    # Fallback local
    os.makedirs(LOCAL_DIR, exist_ok=True)
    path = os.path.join(LOCAL_DIR, fname)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_excel(path)
    except Exception:
        return pd.DataFrame()

def save_base(df: pd.DataFrame, nome: str) -> None:
    """Salva base como Excel no Drive (se disponível) ou no disco local."""
    if df is None:
        df = pd.DataFrame()
    fname = FILES.get(nome, f"{nome}.xlsx")

    # Tenta Drive
    drive = conectar_drive()
    if drive:
        try:
            base_folder = getattr(st, "secrets", {}).get("drive_base_folder", DEFAULT_DRIVE_FOLDER_NAME)
            folder_id = obter_id_pasta(base_folder)
            if folder_id:
                # gera Excel em memória
                mem = io.BytesIO()
                with pd.ExcelWriter(mem, engine="xlsxwriter") as writer:
                    # sheet_name até 31 chars
                    sheet = nome[:31] if nome else "Sheet1"
                    (df if isinstance(df, pd.DataFrame) else pd.DataFrame()).to_excel(writer, index=False, sheet_name=sheet)
                mem.seek(0)

                # procura arquivo existente
                f = _buscar_arquivo(drive, folder_id, fname)
                if f:
                    f.SetContentString("")  # limpa meta
                    f.SetContentFile(None)  # previne cache
                    f.SetContentString("")  # redundância segura
                    # PyDrive precisa de arquivo físico para upload
                    tmp = "upload.xlsx"
                    with open(tmp, "wb") as out:
                        out.write(mem.read())
                    f.SetContentFile(tmp)
                    f.Upload()
                    try: os.remove(tmp)
                    except Exception: pass
                else:
                    newf = drive.CreateFile({'title': fname, 'parents': [{'id': folder_id}]})
                    tmp = "upload.xlsx"
                    with open(tmp, "wb") as out:
                        # re-posiciona ponteiro e grava
                        mem.seek(0)
                        out.write(mem.read())
                    newf.SetContentFile(tmp)
                    newf.Upload()
                    try: os.remove(tmp)
                    except Exception: pass
                return
        except Exception:
            # se der erro no Drive, cai para local
            pass

    # Fallback local
    os.makedirs(LOCAL_DIR, exist_ok=True)
    path = os.path.join(LOCAL_DIR, fname)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        sheet = nome[:31] if nome else "Sheet1"
        (df if isinstance(df, pd.DataFrame) else pd.DataFrame()).to_excel(writer, index=False, sheet_name=sheet)
