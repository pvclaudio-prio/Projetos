"""
Módulo: cadastro_ideias.py
Propósito: Cadastro e gestão de ideias integradas a projetos.
"""

from __future__ import annotations
import io
import os
import uuid
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
import numpy as np
import streamlit as st

# -----------------------------
# Helpers: Google Drive (PyDrive2) — usando o padrão do usuário
# -----------------------------
try:
    import httplib2
    from oauth2client.client import OAuth2Credentials
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
    HAS_GDRIVE = True
except Exception:
    HAS_GDRIVE = False

def conectar_drive():
    if not HAS_GDRIVE:
        return None
    cred_dict = st.secrets.get("credentials")
    if not cred_dict:
        st.warning("Segredo 'credentials' não encontrado em st.secrets.")
        return None
    try:
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
        if not credentials.access_token or credentials.access_token_expired:
            credentials.refresh(httplib2.Http())
        gauth = GoogleAuth()
        # Evita erro "Missing required setting client_config" definindo um client_config mínimo
        gauth.settings["client_config"] = {
            "client_id": cred_dict.get("client_id"),
            "client_secret": cred_dict.get("client_secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "revoke_uri": "https://oauth2.googleapis.com/revoke",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
        gauth.credentials = credentials
        return GoogleDrive(gauth)
    except Exception as e:
        st.warning(f"Falha ao autenticar no Google Drive: {e}")
        return None

# Compat: alias para código antigo que chamava _gdrive_auth()
_gdrive_auth = conectar_drive

def obter_id_pasta(nome_pasta: str, parent_id: str | None = None) -> str | None:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        query = f"title = '{nome_pasta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        resultado = drive.ListFile({'q': query}).GetList()
        if resultado:
            return resultado[0]['id']
        return None
    except Exception:
        return None

def garantir_pasta(nome_pasta: str, parent_id: str | None = None) -> str | None:
    drive = conectar_drive()
    if not drive:
        return None
    pasta_id = obter_id_pasta(nome_pasta, parent_id)
    if pasta_id:
        return pasta_id
    try:
        meta = {'title': nome_pasta, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id:
            meta['parents'] = [{'id': parent_id}]
        folder = drive.CreateFile(meta)
        folder.Upload()
        return folder['id']
    except Exception as e:
        st.warning(f"Não foi possível criar a pasta '{nome_pasta}' no Drive: {e}")
        return None

def _drive_find_file(filename: str, parent_id: str | None) -> str | None:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        query = f"title = '{filename}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        flist = drive.ListFile({'q': query}).GetList()
        return flist[0]['id'] if flist else None
    except Exception:
        return None

def _drive_download_excel(file_id: str) -> pd.DataFrame | None:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        f = drive.CreateFile({'id': file_id})
        tmp = 'temp_download.xlsx'
        f.GetContentFile(tmp)
        df = pd.read_excel(tmp)
        os.remove(tmp)
        return df
    except Exception as e:
        st.warning(f"Falha ao baixar arquivo do Drive: {e}")
        return None

def _drive_upload_excel(df: pd.DataFrame, filename: str, parent_id: str | None) -> str | None:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        temp_path = f"/tmp/{filename}"
        df.to_excel(temp_path, index=False)
        file_id = _drive_find_file(filename, parent_id)
        if file_id:
            f = drive.CreateFile({'id': file_id})
        else:
            meta = {'title': filename}
            if parent_id:
                meta['parents'] = [{'id': parent_id}]
            f = drive.CreateFile(meta)
        f.SetContentFile(temp_path)
        f.Upload()
        os.remove(temp_path)
        return f['id']
    except Exception as e:
        st.warning(f"Falha ao enviar arquivo ao Drive: {e}")
        return None

# -----------------------------
# Persistência
# -----------------------------
class Storage:
    def __init__(self):
        self.pasta_bases = st.secrets.get('pastas', {}).get('pasta_bases', 'bases')
        self.pasta_backups = st.secrets.get('pastas', {}).get('pasta_backups', 'backups')
        self.bases_id = garantir_pasta(self.pasta_bases)
        self.backups_id = garantir_pasta(self.pasta_backups)
    def load_excel(self, filename: str, create_if_missing: bool = True, schema: Optional[dict] = None) -> pd.DataFrame:
        file_id = _drive_find_file(filename, self.bases_id)
        if file_id:
            df = _drive_download_excel(file_id)
            if df is not None:
                return df
        local_path = os.path.join(self.pasta_bases, filename)
        os.makedirs(self.pasta_bases, exist_ok=True)
        if os.path.exists(local_path):
            return pd.read_excel(local_path)
        if create_if_missing:
            df = pd.DataFrame(columns=list(schema.keys()) if schema else [])
            df.to_excel(local_path, index=False)
            return df
        return pd.DataFrame()
    def save_excel(self, df: pd.DataFrame, filename: str):
        self.backup(df, prefix=filename.replace('.xlsx', ''))
        if self.bases_id:
            _drive_upload_excel(df, filename, self.bases_id)
        local_path = os.path.join(self.pasta_bases, filename)
        os.makedirs(self.pasta_bases, exist_ok=True)
        df.to_excel(local_path, index=False)
    def backup(self, df: pd.DataFrame, prefix: str):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"{prefix}_backup_{ts}.xlsx"
        if self.backups_id:
            _drive_upload_excel(df, fname, self.backups_id)
        os.makedirs(self.pasta_backups, exist_ok=True)
        df.to_excel(os.path.join(self.pasta_backups, fname), index=False)

IDEIAS_SCHEMA = { 'id': str, 'titulo': str, 'descricao': str, 'area': str, 'prioridade': str, 'projeto_relacionado': str, 'nome_projeto': str, 'complexidade': int, 'impacto': int, 'confianca': int, 'alcance': int, 'esforco': int, 'score_ICE': float, 'score_RICE': float, 'status': str, 'autor': str, 'tags': str, 'anexos': str, 'data_criacao': str, 'data_atualizacao': str }

def _ensure_columns(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    for col, _ in schema.items():
        if col not in df.columns:
            df[col] = np.nan
    return df[list(schema.keys())]

def _calc_scores(alcance: int, impacto: int, confianca: int, esforco: int, complexidade: int) -> Tuple[float, float]:
    score_ice = round((impacto * confianca) / max(esforco, 1), 2)
    score_rice = round((alcance * impacto * confianca) / max(esforco, 1), 2)
    score_ice = round(score_ice / (1 + (complexidade - 1) * 0.05), 2)
    score_rice = round(score_rice / (1 + (complexidade - 1) * 0.05), 2)
    return score_ice, score_rice

def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def aba_cadastro_ideias():
    st.title("💡 Cadastro & Gestão de Ideias")
    storage = Storage()
    df_projetos = storage.load_excel('projetos.xlsx', create_if_missing=True, schema={ 'project_id': str, 'nome_projeto': str, 'status': str })
    df_ideias = storage.load_excel('ideias.xlsx', create_if_missing=True, schema=IDEIAS_SCHEMA)
    df_ideias = _ensure_columns(df_ideias, IDEIAS_SCHEMA)
    with st.expander("➕ Nova ideia", expanded=False):
        with st.form("form_nova_ideia", clear_on_submit=True):
            col1, col2 = st.columns(2)
            titulo = col1.text_input("Título *")
            area = col2.text_input("Área/Time")
            descricao = st.text_area("Descrição *", height=120)
            col3, col4, col5 = st.columns(3)
            prioridade = col3.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Crítica"], index=1)
            projeto_nome = col4.selectbox("Projeto relacionado (opcional)", ["<sem projeto>"] + df_projetos.get('nome_projeto', pd.Series([])).dropna().unique().tolist())
            autor = col5.text_input("Autor")
            col6, col7, col8, col9, col10 = st.columns(5)
            alcance = int(col6.number_input("Alcance (1-5)", 1, 5, 3))
            impacto = int(col7.number_input("Impacto (1-5)", 1, 5, 3))
            confianca = int(col8.number_input("Confiança (1-5)", 1, 5, 3))
            esforco = int(col9.number_input("Esforço (1-5)", 1, 5, 3))
            complexidade = int(col10.number_input("Complexidade (1-5)", 1, 5, 3))
            tags = st.text_input("Tags")
            anexos = st.text_input("Links de anexos")
            submit = st.form_submit_button("Cadastrar ideia")
            if submit:
                if not titulo or not descricao:
                    st.error("Título e descrição são obrigatórios.")
                else:
                    idea_id = str(uuid.uuid4())
                    now = datetime.now().isoformat(timespec='seconds')
                    proj_id = None
                    if projeto_nome and projeto_nome != "<sem projeto>" and 'nome_projeto' in df_projetos.columns:
                        row = df_projetos[df_projetos['nome_projeto'] == projeto_nome]
                        if not row.empty and 'project_id' in row.columns:
                            proj_id = str(row.iloc[0]['project_id'])
                    score_ice, score_rice = _calc_scores(alcance, impacto, confianca, esforco, complexidade)
                    new_row = { 'id': idea_id, 'titulo': titulo, 'descricao': descricao, 'area': area, 'prioridade': prioridade, 'projeto_relacionado': proj_id, 'nome_projeto': projeto_nome if projeto_nome and projeto_nome != "<sem projeto>" else "", 'complexidade': complexidade, 'impacto': impacto, 'confianca': confianca, 'alcance': alcance, 'esforco': esforco, 'score_ICE': score_ice, 'score_RICE': score_rice, 'status': 'Novo', 'autor': autor, 'tags': tags, 'anexos': anexos, 'data_criacao': now, 'data_atualizacao': now }
                    df_ideias = pd.concat([df_ideias, pd.DataFrame([new_row])], ignore_index=True)
                    storage.save_excel(df_ideias, 'ideias.xlsx')
                    st.success("Ideia cadastrada com sucesso!")
    st.subheader("🔎 Filtro & Busca")
    colf1, colf2, colf3, colf4 = st.columns(4)
    filtro_status = colf1.multiselect("Status", ["Novo", "Em avaliação", "Aprovado", "Rejeitado", "Em andamento", "Concluído"], default=[])
    filtro_prioridade = colf2.multiselect("Prioridade", ["Baixa", "Média", "Alta", "Crítica"], default=[])
    filtro_projeto = colf3.multiselect("Projeto", df_ideias['nome_projeto'].dropna().replace('', np.nan).dropna().unique().tolist())
    busca_texto = colf4.text_input("Busca (título/descrição/tags)")
    df_view = df_ideias.copy()
    if filtro_status:
        df_view = df_view[df_view['status'].isin(filtro_status)]
    if filtro_prioridade:
        df_view = df_view[df_view['prioridade'].isin(filtro_prioridade)]
    if filtro_projeto:
        df_view = df_view[df_view['nome_projeto'].isin(filtro_projeto)]
    if busca_texto:
        mask = (df_view['titulo'].fillna('').str.contains(busca_texto, case=False) | df_view['descricao'].fillna('').str.contains(busca_texto, case=False) | df_view['tags'].fillna('').str.contains(busca_texto, case=False))
        df_view = df_view[mask]
    st.dataframe(df_view.drop(columns=['descricao']), use_container_width=True, hide_index=True)
    st.subheader("✏️ Edição rápida / Status")
    colu1, colu2, colu3 = st.columns([3, 2, 2])
    idea_id_sel = colu1.selectbox("Selecione a ideia", ["<selecione>"] + df_ideias['titulo'].fillna('').tolist())
    novo_status = colu2.selectbox("Novo status", ["Novo", "Em avaliação", "Aprovado", "Rejeitado", "Em andamento", "Concluído"], index=0)
    acao = colu3.selectbox("Ação", ["Atualizar status", "Recalcular scores", "Excluir ideia"], index=0)
    if st.button("Executar ação", type="primary"):
        if idea_id_sel == "<selecione>":
            st.error("Selecione uma ideia.")
        else:
            idx = df_ideias[df_ideias['titulo'] == idea_id_sel].index
            if len(idx) == 0:
                st.error("Ideia não encontrada.")
            else:
                i = idx[0]
                if acao == "Atualizar status":
                    df_ideias.at[i, 'status'] = novo_status
                    df_ideias.at[i, 'data_atualizacao'] = datetime.now().isoformat(timespec='seconds')
                    storage.save_excel(df_ideias, 'ideias.xlsx')
                    st.success("Status atualizado.")
                elif acao == "Recalcular scores":
                    ice, rice = _calc_scores(int(df_ideias.at[i, 'alcance'] or 3), int(df_ideias.at[i, 'impacto'] or 3), int(df_ideias.at[i, 'confianca'] or 3), int(df_ideias.at[i, 'esforco'] or 3), int(df_ideias.at[i, 'complexidade'] or 3))
                    df_ideias.at[i, 'score_ICE'] = ice
                    df_ideias.at[i, 'score_RICE'] = rice
                    df_ideias.at[i, 'data_atualizacao'] = datetime.now().isoformat(timespec='seconds')
                    storage.save_excel(df_ideias, 'ideias.xlsx')
                    st.success("Scores recalculados.")
                elif acao == "Excluir ideia":
                    df_ideias = df_ideias.drop(index=i).reset_index(drop=True)
                    storage.save_excel(df_ideias, 'ideias.xlsx')
                    st.success("Ideia excluída.")
    st.subheader("📤 Exportações")
    colx1, colx2 = st.columns
