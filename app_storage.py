# -*- coding: utf-8 -*-
from __future__ import annotations
import os, io
from typing import Optional, Dict
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
    # cria um shunt mínimo para evitar NameError quando importado fora do Streamlit
    class _Dummy:
        secrets = {}
    st = _Dummy()  # type: ignore

# -----------------------------
# Config
# -----------------------------
LOCAL_DIR = os.environ.get("APP_DATA_DIR", "./data_excel")

FILES: Dict[str, str] = {
    "projetos": "projetos.xlsx",
    "atividades": "atividades.xlsx",
    "financeiro": "financeiro_projeto.xlsx",
    "pontos_focais": "pontos_focais.xlsx",
    "riscos": "riscos.xlsx",
}

DEFAULT_DRIVE_FOLDER_NAME = "GestaoProjetosApp"

# -----------------------------
# Autenticação & utilitários Drive
# -----------------------------
def _get_secrets() -> dict:
    try:
        return dict(getattr(st, "secrets", {}))
    except Exception:
        return {}

def conectar_drive() -> Optional[GoogleDrive]:
    """Autentica no Google Drive usando o modelo OAuth em st.secrets['credentials'].
    Lança exceção em falha para que o caller decida fallback."""
    if not HAS_GDRIVE:
        return None

    secrets = _get_secrets()
    cred_dict = secrets.get("credentials")
    if not cred_dict:
        # Sem credenciais, sem Drive.
        return None

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

    if (not credentials.access_token) or getattr(credentials, "access_token_expired", False):
        # refresh pode lançar; deixe a exceção subir
        credentials.refresh(httplib2.Http())

    gauth = GoogleAuth()
    # Evita erro "Missing required setting client_config"
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

def _obter_id_pasta_por_nome(drive: GoogleDrive, nome_pasta: str, parent_id: Optional[str] = None) -> Optional[str]:
    # PyDrive (Drive v2) usa 'title'
    query = f"title = '{nome_pasta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    lst = drive.ListFile({'q': query}).GetList()
    if lst:
        return lst[0]['id']
    # criar se não existir
    folder = drive.CreateFile({
        'title': nome_pasta,
        'mimeType': 'application/vnd.google-apps.folder'
    })
    if parent_id:
        folder['parents'] = [{'id': parent_id}]
    folder.Upload()
    return folder['id']

def obter_id_pasta_base(drive: GoogleDrive) -> Optional[str]:
    secrets = _get_secrets()
    # prioridade: id explícito > nome
    folder_id = secrets.get("drive_base_folder_id")
    if folder_id:
        return folder_id
    folder_name = secrets.get("drive_base_folder", DEFAULT_DRIVE_FOLDER_NAME)
    return _obter_id_pasta_por_nome(drive, folder_name)

def _buscar_arquivo_por_titulo(drive: GoogleDrive, parent_id: str, titulo: str):
    q = f"'{parent_id}' in parents and title = '{titulo}' and trashed = false"
    lst = drive.ListFile({'q': q}).GetList()
    return lst[0] if lst else None

def _baixar_excel_por_id(drive: GoogleDrive, file_id: str) -> pd.DataFrame:
    f = drive.CreateFile({'id': file_id})
    # Baixar para BytesIO (PyDrive precisa de arquivo físico; contornamos com tmp)
    tmp = "download_tmp.xlsx"
    f.GetContentFile(tmp)
    try:
        with open(tmp, "rb") as fh:
            mem = io.BytesIO(fh.read())
        mem.seek(0)
        return pd.read_excel(mem)
    finally:
        try: os.remove(tmp)
        except Exception: pass

def _upload_excel_por_id(drive: GoogleDrive, file_id: str, df: pd.DataFrame, sheet_name: str):
    # Prepara Excel em arquivo temporário e faz upload (update)
    tmp = "upload_tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="xlsxwriter") as writer:
        (df if isinstance(df, pd.DataFrame) else pd.DataFrame())\
            .to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Sheet1")
    f = drive.CreateFile({'id': file_id})
    f.SetContentFile(tmp)
    f.Upload()  # mantém o mesmo fileId (nova revisão)
    try: os.remove(tmp)
    except Exception: pass

def _criar_arquivo_excel(drive: GoogleDrive, parent_id: str, titulo: str, df: pd.DataFrame, sheet_name: str) -> str:
    tmp = "upload_new_tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="xlsxwriter") as writer:
        (df if isinstance(df, pd.DataFrame) else pd.DataFrame())\
            .to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Sheet1")
    newf = drive.CreateFile({'title': titulo, 'parents': [{'id': parent_id}]})
    newf.SetContentFile(tmp)
    newf.Upload()
    try: os.remove(tmp)
    except Exception: pass
    return newf['id']

# -----------------------------
# Leitura/Gravação Excel (Drive ou local)
# -----------------------------
def load_base(nome: str) -> pd.DataFrame:
    """Carrega base a partir do Drive (prioritário) ou do disco local.
    Lança exceção se o Drive estiver configurado mas a leitura falhar."""
    fname = FILES.get(nome, f"{nome}.xlsx")
    secrets = _get_secrets()

    # 1) Tenta Drive se houver credenciais
    drive = conectar_drive()
    if drive:
        # Se houver fileId específico para a base, usa direto
        file_id_map = (secrets.get("drive", {}) or {}).get("file_ids", {})
        file_id = file_id_map.get(nome)
        try:
            if file_id:
                return _baixar_excel_por_id(drive, file_id)
            # Senão, procura por título na pasta base
            folder_id = obter_id_pasta_base(drive)
            if folder_id:
                f = _buscar_arquivo_por_titulo(drive, folder_id, fname)
                if f:
                    return _baixar_excel_por_id(drive, f['id'])
                else:
                    # Não existe no Drive ainda → retorna vazio (sem exceção)
                    return pd.DataFrame()
            else:
                raise RuntimeError("Não foi possível resolver a pasta base do Drive.")
        except Exception as e:
            # Propaga a falha para que o caller decida fallback/erro
            raise

    # 2) Fallback local (sem Drive)
    os.makedirs(LOCAL_DIR, exist_ok=True)
    path = os.path.join(LOCAL_DIR, fname)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_excel(path)
    except Exception:
        return pd.DataFrame()

def save_base(df: pd.DataFrame, nome: str) -> None:
    """Salva base no Drive se disponível (criando arquivo se não existir).
    Lança exceção se o Drive estiver configurado e a gravação falhar.
    Sempre mantém uma cópia local como backup."""
    if df is None:
        df = pd.DataFrame()
    fname = FILES.get(nome, f"{nome}.xlsx")
    secrets = _get_secrets()

    # 1) Tenta salvar no Drive (se houver credenciais)
    drive = conectar_drive()
    if drive:
        sheet = (nome or "Sheet1")[:31]
        # Prioriza fileId se fornecido em secrets
        file_id_map = (secrets.get("drive", {}) or {}).get("file_ids", {})
        file_id = file_id_map.get(nome)

        try:
            if file_id:
                _upload_excel_por_id(drive, file_id, df, sheet)
            else:
                folder_id = obter_id_pasta_base(drive)
                if not folder_id:
                    raise RuntimeError("Não foi possível resolver a pasta base do Drive.")
                f = _buscar_arquivo_por_titulo(drive, folder_id, fname)
                if f:
                    _upload_excel_por_id(drive, f['id'], df, sheet)
                else:
                    # cria novo arquivo
                    new_id = _criar_arquivo_excel(drive, folder_id, fname, df, sheet)
                    # opcional: se você quiser fixar o id criado nos secrets em runtime, poderia armazenar em session_state
                    # mas geralmente isso é gerenciado fora do código
        except Exception as e:
            # Propaga a falha para que o caller (common.save_base) trate e faça fallback local explícito
            raise

    # 2) Sempre salva cópia local (backup)
    os.makedirs(LOCAL_DIR, exist_ok=True)
    path = os.path.join(LOCAL_DIR, fname)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        sheet = (nome or "Sheet1")[:31]
        (df if isinstance(df, pd.DataFrame) else pd.DataFrame())\
            .to_excel(writer, index=False, sheet_name=sheet)
