"""
Módulo: visualizacao_unificada.py
Propósito: Aba de Visualização Unificada de Projetos, Ideias e Riscos
Stack: Streamlit, Pandas, PyDrive2, OAuth2Credentials (modelo do usuário), UUID, datetime
Armazenamento: Google Drive (pastas "bases" e "backups") + fallback local

Lê as bases:
- bases/projetos.xlsx      (colunas mín.: project_id, nome_projeto, status)
- bases/ideias.xlsx        (ver schema do módulo cadastro_ideias)
- bases/riscos.xlsx        (ver schema do módulo cadastro_riscos)

Recursos:
- KPI cards consolidados
- Filtros por projeto, status (projeto/ideias/riscos), prioridade, categoria
- Tabelas com drill simples (seleção de projeto)
- Painel por projeto (riscos por severidade, ideias por status)
- Top 10 ideias por ICE/RICE
- Exportação Excel com múltiplas abas (snapshot do filtro)

Integração:
- `registrar_pagina(router)` para adicionar a página ao menu
- `visualizacao_unificada()` para compatibilidade
"""

from __future__ import annotations
import io
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st

# -----------------------------
# Helpers: Google Drive (PyDrive2) — padrão do usuário
# -----------------------------
try:
    import httplib2
    from oauth2client.client import OAuth2Credentials
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
    HAS_GDRIVE = True
except Exception:
    HAS_GDRIVE = False


def conectar_drive() -> Optional[GoogleDrive]:
    if not HAS_GDRIVE:
        return None
    cred_dict = st.secrets.get("credentials")
    if not cred_dict:
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

# Compat alias para código legado
_gdrive_auth = conectar_drive


def garantir_pasta(nome_pasta: str, parent_id: Optional[str] = None) -> Optional[str]:
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
        meta = {'title': nome_pasta, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id:
            meta['parents'] = [{'id': parent_id}]
        folder = drive.CreateFile(meta)
        folder.Upload()
        return folder['id']
    except Exception:
        return None


def _drive_find_file(filename: str, parent_id: Optional[str]) -> Optional[str]:
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


def _drive_download_excel(file_id: str) -> Optional[pd.DataFrame]:
    drive = conectar_drive()
    if not drive:
        return None
    try:
        f = drive.CreateFile({'id': file_id})
        tmp = 'temp_unificada.xlsx'
        f.GetContentFile(tmp)
        df = pd.read_excel(tmp)
        os.remove(tmp)
        return df
    except Exception:
        return None


class Storage:
    def __init__(self):
        self.pasta_bases = st.secrets.get('pastas', {}).get('pasta_bases', 'bases')
        self.pasta_backups = st.secrets.get('pastas', {}).get('pasta_backups', 'backups')
        self.bases_id = garantir_pasta(self.pasta_bases)

    def load_excel(self, filename: str, create_if_missing: bool = False, schema: Optional[dict] = None) -> pd.DataFrame:
        file_id = _drive_find_file(filename, self.bases_id)
        if file_id:
            df = _drive_download_excel(file_id)
            if df is not None:
                return df
        local_path = os.path.join(self.pasta_bases, filename)
        if os.path.exists(local_path):
            return pd.read_excel(local_path)
        if create_if_missing:
            df = pd.DataFrame(columns=list(schema.keys()) if schema else [])
            os.makedirs(self.pasta_bases, exist_ok=True)
            df.to_excel(local_path, index=False)
            return df
        return pd.DataFrame()


# -----------------------------
# Página
# -----------------------------

def _kpi_card_cols(df_proj: pd.DataFrame, df_ide: pd.DataFrame, df_risk: pd.DataFrame):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projetos", int(df_proj.shape[0]))
    c2.metric("Ideias", int(df_ide.shape[0]))
    c3.metric("Riscos", int(df_risk.shape[0]))
    criticos = int((pd.to_numeric(df_risk.get('severidade', pd.Series([])), errors='coerce') >= 20).sum())
    c4.metric("Riscos críticos (≥20)", criticos)


def _filters(df_proj: pd.DataFrame):
    st.subheader("Filtros")
    col1, col2, col3, col4 = st.columns(4)
    projeto = col1.multiselect("Projeto", df_proj.get('nome_projeto', pd.Series([])).dropna().unique().tolist())
    status_proj = col2.multiselect("Status do projeto", df_proj.get('status', pd.Series([])).dropna().unique().tolist())
    status_ideia = col3.multiselect("Status da ideia", ["Novo", "Em avaliação", "Aprovado", "Rejeitado", "Em andamento", "Concluído"]) 
    categoria_risco = col4.multiselect("Categoria do risco", ["Estratégico", "Operacional", "Financeiro", "Compliance", "TI", "Segurança", "Outros"]) 
    return projeto, status_proj, status_ideia, categoria_risco


def _apply_filters(df_proj, df_ide, df_risk, projeto, status_proj, status_ideia, categoria_risco):
    if projeto:
        df_proj = df_proj[df_proj['nome_projeto'].isin(projeto)]
        df_ide = df_ide[df_ide['nome_projeto'].isin(projeto)]
        df_risk = df_risk[df_risk['nome_projeto'].isin(projeto)]
    if status_proj:
        df_proj = df_proj[df_proj['status'].isin(status_proj)]
    if status_ideia:
        df_ide = df_ide[df_ide['status'].isin(status_ideia)]
    if categoria_risco:
        df_risk = df_risk[df_risk['categoria'].isin(categoria_risco)]
    return df_proj, df_ide, df_risk


def _painel_por_projeto(df_proj, df_ide, df_risk):
    st.subheader("Painel por Projeto")
    # agregações
    ideias_por_status = df_ide.groupby(['nome_projeto','status']).size().reset_index(name='qtd')
    riscos_por_sev = df_risk.assign(sev=pd.to_numeric(df_risk['severidade'], errors='coerce')).groupby(['nome_projeto','sev']).size().reset_index(name='qtd')

    col1, col2 = st.columns(2)
    with col1:
        st.write("Ideias por status (tabela)")
        if ideias_por_status.empty:
            st.info("Sem dados de ideias para os filtros.")
        else:
            piv1 = ideias_por_status.pivot_table(index='nome_projeto', columns='status', values='qtd', aggfunc='sum', fill_value=0)
            st.dataframe(piv1, use_container_width=True)
    with col2:
        st.write("Riscos por severidade (tabela)")
        if riscos_por_sev.empty:
            st.info("Sem dados de riscos para os filtros.")
        else:
            piv2 = riscos_por_sev.pivot_table(index='nome_projeto', columns='sev', values='qtd', aggfunc='sum', fill_value=0).sort_index(axis=1)
            st.dataframe(piv2, use_container_width=True)


def _tops(df_ide):
    st.subheader("Top 10 Ideias (RICE e ICE)")
    col1, col2 = st.columns(2)
    if 'score_RICE' in df_ide.columns and not df_ide.empty:
        top_rice = df_ide.sort_values('score_RICE', ascending=False).head(10)[['titulo','nome_projeto','prioridade','score_RICE','status']]
        with col1:
            st.write("Top RICE")
            st.dataframe(top_rice, use_container_width=True, hide_index=True)
    else:
        with col1:
            st.info("Base de ideias sem coluna 'score_RICE' ou vazia.")
    if 'score_ICE' in df_ide.columns and not df_ide.empty:
        top_ice = df_ide.sort_values('score_ICE', ascending=False).head(10)[['titulo','nome_projeto','prioridade','score_ICE','status']]
        with col2:
            st.write("Top ICE")
            st.dataframe(top_ice, use_container_width=True, hide_index=True)
    else:
        with col2:
            st.info("Base de ideias sem coluna 'score_ICE' ou vazia.")


def _exportar_snapshot(df_proj, df_ide, df_risk):
    st.subheader("Exportar snapshot (Excel)")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df_proj.to_excel(writer, index=False, sheet_name='projetos')
        df_ide.to_excel(writer, index=False, sheet_name='ideias')
        df_risk.to_excel(writer, index=False, sheet_name='riscos')
    st.download_button("Baixar Excel", data=buf.getvalue(), file_name=f"unificada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")


def aba_visualizacao_unificada():
    st.title("📊 Visualização Unificada — Projetos, Ideias e Riscos")
    store = Storage()

    # Carrega bases
    df_proj = store.load_excel('projetos.xlsx', create_if_missing=True, schema={'project_id': str, 'nome_projeto': str, 'status': str})
    df_ide = store.load_excel('ideias.xlsx', create_if_missing=True, schema={})
    df_risk = store.load_excel('riscos.xlsx', create_if_missing=True, schema={})

    # Normalizações leves
    for df in (df_proj, df_ide, df_risk):
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)

    _kpi_card_cols(df_proj, df_ide, df_risk)
    projeto, status_proj, status_ideia, categoria_risco = _filters(df_proj)
    df_proj_f, df_ide_f, df_risk_f = _apply_filters(df_proj, df_ide, df_risk, projeto, status_proj, status_ideia, categoria_risco)

    st.markdown("---")
    _painel_por_projeto(df_proj_f, df_ide_f, df_risk_f)

    st.markdown("---")
    colA, colB = st.columns(2)
    with colA:
        st.subheader("Ideias (filtradas)")
        mostrar_cols_ide = [c for c in df_ide_f.columns if c not in ['descricao','anexos']]
        st.dataframe(df_ide_f[mostrar_cols_ide], use_container_width=True, hide_index=True)
    with colB:
        st.subheader("Riscos (filtrados)")
        mostrar_cols_risk = [c for c in df_risk_f.columns if c not in ['descricao','plano_mitigacao','anexos']]
        st.dataframe(df_risk_f[mostrar_cols_risk], use_container_width=True, hide_index=True)

    st.markdown("---")
    _tops(df_ide_f)

    st.markdown("---")
    _exportar_snapshot(df_proj_f, df_ide_f, df_risk_f)


# -----------------------------
# Integração com o app principal
# -----------------------------

def registrar_pagina(router: dict):
    router["📊 Visualização Unificada"] = aba_visualizacao_unificada

# Compat

def visualizacao_unificada():
    return aba_visualizacao_unificada()


if __name__ == "__main__":
    aba_visualizacao_unificada()
