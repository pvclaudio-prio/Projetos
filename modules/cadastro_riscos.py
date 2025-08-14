"""
Módulo: cadastro_riscos.py
Propósito: Abas de Cadastro e Gestão de Riscos integradas aos Projetos.
Stack: Streamlit, Pandas, PyDrive2, OAuth2Credentials (modelo do usuário), UUID, datetime
Armazenamento: Google Drive (pasta "bases" e "backups") + fallback local

Segredos esperados (modelo do usuário) em .streamlit/secrets.toml:
[credentials]
access_token = ""
client_id = "SUA_CLIENT_ID.apps.googleusercontent.com"
client_secret = "SEU_CLIENT_SECRET"
refresh_token = "SEU_REFRESH_TOKEN"
token_expiry = "2099-01-01T00:00:00Z"
token_uri = "https://oauth2.googleapis.com/token"
revoke_uri = "https://oauth2.googleapis.com/revoke"
user_agent = "streamlit-app/1.0"

[pastas]
pasta_bases = "bases"
pasta_backups = "backups"
"""

from __future__ import annotations
import io
import os
import uuid
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
    """Autentica no Google Drive usando st.secrets["credentials"]."""
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
    except Exception as e:
        st.warning(f"Falha ao autenticar no Google Drive: {e}")
        return None


# Compat: alias para código antigo
_gdrive_auth = conectar_drive


def obter_id_pasta(nome_pasta: str, parent_id: Optional[str] = None) -> Optional[str]:
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


def garantir_pasta(nome_pasta: str, parent_id: Optional[str] = None) -> Optional[str]:
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
        tmp = 'temp_riscos_download.xlsx'
        f.GetContentFile(tmp)
        df = pd.read_excel(tmp)
        os.remove(tmp)
        return df
    except Exception as e:
        st.warning(f"Falha ao baixar arquivo do Drive: {e}")
        return None


def _drive_upload_excel(df: pd.DataFrame, filename: str, parent_id: Optional[str]) -> Optional[str]:
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
# Persistência (Drive + Fallback Local)
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


# -----------------------------
# Domínio: Riscos
# -----------------------------
RISCOS_SCHEMA = {
    'id': str,
    'titulo': str,
    'descricao': str,
    'categoria': str,  # Estratégico, Operacional, Financeiro, Compliance, TI, Segurança, Outros
    'processo': str,
    'projeto_relacionado': str,
    'nome_projeto': str,
    'probabilidade': int,
    'impacto': int,
    'severidade': int,
    'risco_inerente': int,
    'estrategia_tratamento': str,
    'plano_mitigacao': str,
    'responsavel': str,
    'prazo_mitigacao': str,
    'custo_mitigacao': float,
    'prob_residual': int,
    'impacto_residual': int,
    'risco_residual': int,
    'status': str,  # Aberto, Em mitigação, Aceito, Transferido, Fechado
    'tags': str,
    'anexos': str,
    'data_criacao': str,
    'data_atualizacao': str,
}


def _ensure_columns(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    for col in schema.keys():
        if col not in df.columns:
            df[col] = np.nan
    return df[list(schema.keys())]


def _calc_severidade(prob: int, imp: int) -> int:
    try:
        p = max(1, min(5, int(prob)))
        i = max(1, min(5, int(imp)))
        return int(p * i)
    except Exception:
        return 1


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# -----------------------------
# UI Principal
# -----------------------------

def aba_cadastro_riscos():
    st.title("🚩 Cadastro & Gestão de Riscos")
    storage = Storage()

    # Carrega bases
    df_projetos = storage.load_excel('projetos.xlsx', create_if_missing=True, schema={
        'project_id': str, 'nome_projeto': str, 'status': str
    })
    df_riscos = storage.load_excel('riscos.xlsx', create_if_missing=True, schema=RISCOS_SCHEMA)
    df_riscos = _ensure_columns(df_riscos, RISCOS_SCHEMA)

    with st.expander("➕ Novo risco", expanded=False):
        with st.form("form_novo_risco", clear_on_submit=True):
            col1, col2 = st.columns(2)
            titulo = col1.text_input("Título *")
            categoria = col2.selectbox("Categoria", [
                "Estratégico", "Operacional", "Financeiro", "Compliance", "TI", "Segurança", "Outros"
            ])

            descricao = st.text_area("Descrição *", height=140)
            processo = st.text_input("Processo/Atividade")

            col3, col4, col5 = st.columns(3)
            projeto_nome = col3.selectbox("Projeto relacionado (opcional)", ["<sem projeto>"] + df_projetos.get('nome_projeto', pd.Series([])).dropna().unique().tolist())
            responsavel = col4.text_input("Responsável")
            prazo_mitigacao = col5.date_input("Prazo de mitigação")

            col6, col7, col8 = st.columns(3)
            prob = int(col6.number_input("Probabilidade (1-5)", 1, 5, 3))
            imp = int(col7.number_input("Impacto (1-5)", 1, 5, 3))
            estrategia = col8.selectbox("Estratégia", ["Evitar", "Reduzir", "Transferir", "Aceitar"])

            plano_mitigacao = st.text_area("Plano de mitigação", help="Descreva ações, responsáveis secundários, marcos e evidências esperadas")

            col9, col10, col11 = st.columns(3)
            prob_res = int(col9.number_input("Prob. residual (1-5)", 1, 5, 3))
            imp_res = int(col10.number_input("Impacto residual (1-5)", 1, 5, 3))
            custo_mit = float(col11.number_input("Custo de mitigação (R$)", 0.0, step=100.0))

            tags = st.text_input("Tags (separe por vírgulas)")
            anexos = st.text_input("Links de anexos (separe por vírgulas)")

            submit = st.form_submit_button("Cadastrar risco")

            if submit:
                if not titulo or not descricao:
                    st.error("Título e descrição são obrigatórios.")
                else:
                    risk_id = str(uuid.uuid4())
                    now = datetime.now().isoformat(timespec='seconds')
                    proj_id = None
                    if projeto_nome and projeto_nome != "<sem projeto>" and 'nome_projeto' in df_projetos.columns:
                        row = df_projetos[df_projetos['nome_projeto'] == projeto_nome]
                        if not row.empty and 'project_id' in row.columns:
                            proj_id = str(row.iloc[0]['project_id'])
                    severidade = _calc_severidade(prob, imp)
                    risco_residual = _calc_severidade(prob_res, imp_res)

                    new_row = {
                        'id': risk_id,
                        'titulo': titulo,
                        'descricao': descricao,
                        'categoria': categoria,
                        'processo': processo,
                        'projeto_relacionado': proj_id,
                        'nome_projeto': projeto_nome if projeto_nome and projeto_nome != "<sem projeto>" else "",
                        'probabilidade': prob,
                        'impacto': imp,
                        'severidade': severidade,
                        'risco_inerente': severidade,
                        'estrategia_tratamento': estrategia,
                        'plano_mitigacao': plano_mitigacao,
                        'responsavel': responsavel,
                        'prazo_mitigacao': prazo_mitigacao.isoformat() if prazo_mitigacao else "",
                        'custo_mitigacao': custo_mit,
                        'prob_residual': prob_res,
                        'impacto_residual': imp_res,
                        'risco_residual': risco_residual,
                        'status': 'Aberto',
                        'tags': tags,
                        'anexos': anexos,
                        'data_criacao': now,
                        'data_atualizacao': now,
                    }
                    df_riscos = pd.concat([df_riscos, pd.DataFrame([new_row])], ignore_index=True)
                    storage.save_excel(df_riscos, 'riscos.xlsx')
                    st.success("Risco cadastrado com sucesso!")

    st.subheader("🔎 Filtro & Busca")
    colf1, colf2, colf3, colf4, colf5 = st.columns(5)
    filtro_status = colf1.multiselect("Status", ["Aberto", "Em mitigação", "Aceito", "Transferido", "Fechado"], default=[])
    filtro_categoria = colf2.multiselect("Categoria", ["Estratégico", "Operacional", "Financeiro", "Compliance", "TI", "Segurança", "Outros"], default=[])
    filtro_projeto = colf3.multiselect("Projeto", df_riscos['nome_projeto'].dropna().replace('', np.nan).dropna().unique().tolist())
    filtro_responsavel = colf4.text_input("Responsável contém…")
    busca_texto = colf5.text_input("Busca (título/descrição/tags)")

    df_view = df_riscos.copy()
    if filtro_status:
        df_view = df_view[df_view['status'].isin(filtro_status)]
    if filtro_categoria:
        df_view = df_view[df_view['categoria'].isin(filtro_categoria)]
    if filtro_projeto:
        df_view = df_view[df_view['nome_projeto'].isin(filtro_projeto)]
    if filtro_responsavel:
        df_view = df_view[df_view['responsavel'].fillna('').str.contains(filtro_responsavel, case=False)]
    if busca_texto:
        mask = (
            df_view['titulo'].fillna('').str.contains(busca_texto, case=False) |
            df_view['descricao'].fillna('').str.contains(busca_texto, case=False) |
            df_view['tags'].fillna('').str.contains(busca_texto, case=False)
        )
        df_view = df_view[mask]

    st.write("Resultados:")
    mostrar_cols = [c for c in df_view.columns if c not in ['descricao','plano_mitigacao','anexos']]
    st.dataframe(df_view[mostrar_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("✏️ Edição rápida / Status & Residual")
    colu1, colu2, colu3, colu4 = st.columns([3, 2, 2, 2])
    titulo_sel = colu1.selectbox("Selecione o risco (por título)", ["<selecione>"] + df_riscos['titulo'].fillna('').tolist())
    novo_status = colu2.selectbox("Novo status", ["Aberto", "Em mitigação", "Aceito", "Transferido", "Fechado"], index=0)
    acao = colu3.selectbox("Ação", ["Atualizar status", "Recalcular severidades", "Excluir risco"], index=0)
    nova_estrategia = colu4.selectbox("Estratégia", ["Evitar", "Reduzir", "Transferir", "Aceitar"], index=1)

    if st.button("Executar ação", type="primary"):
        if titulo_sel == "<selecione>":
            st.error("Selecione um risco.")
        else:
            idx = df_riscos[df_riscos['titulo'] == titulo_sel].index
            if len(idx) == 0:
                st.error("Risco não encontrado.")
            else:
                i = idx[0]
                if acao == "Atualizar status":
                    df_riscos.at[i, 'status'] = novo_status
                    df_riscos.at[i, 'estrategia_tratamento'] = nova_estrategia
                    df_riscos.at[i, 'data_atualizacao'] = datetime.now().isoformat(timespec='seconds')
                    storage.save_excel(df_riscos, 'riscos.xlsx')
                    st.success("Status/estratégia atualizados.")
                elif acao == "Recalcular severidades":
                    sev = _calc_severidade(int(df_riscos.at[i, 'probabilidade'] or 3), int(df_riscos.at[i, 'impacto'] or 3))
                    sev_res = _calc_severidade(int(df_riscos.at[i, 'prob_residual'] or 3), int(df_riscos.at[i, 'impacto_residual'] or 3))
                    df_riscos.at[i, 'severidade'] = sev
                    df_riscos.at[i, 'risco_inerente'] = sev
                    df_riscos.at[i, 'risco_residual'] = sev_res
                    df_riscos.at[i, 'data_atualizacao'] = datetime.now().isoformat(timespec='seconds')
                    storage.save_excel(df_riscos, 'riscos.xlsx')
                    st.success("Severidades recalculadas.")
                elif acao == "Excluir risco":
                    df_riscos = df_riscos.drop(index=i).reset_index(drop=True)
                    storage.save_excel(df_riscos, 'riscos.xlsx')
                    st.success("Risco excluído.")

    st.markdown("---")
    st.subheader("📊 Painel rápido")
    colk1, colk2, colk3, colk4 = st.columns(4)
    total = int(df_view.shape[0])
    criticos = int((df_view['severidade'] >= 20).sum())
    em_mitigacao = int((df_view['status'] == 'Em mitigação').sum())
    fechados = int((df_view['status'] == 'Fechado').sum())

    colk1.metric("Total de riscos", total)
    colk2.metric("Críticos (≥20)", criticos)
    colk3.metric("Em mitigação", em_mitigacao)
    colk4.metric("Fechados", fechados)

    st.write("Matriz de Risco (contagem por Probabilidade x Impacto)")
    matriz = (
        df_view.assign(prob=lambda d: pd.to_numeric(d['probabilidade'], errors='coerce').fillna(0).astype(int),
                       imp=lambda d: pd.to_numeric(d['impacto'], errors='coerce').fillna(0).astype(int))
               .groupby(['prob','imp']).size().unstack(fill_value=0)
               .reindex(index=[1,2,3,4,5], columns=[1,2,3,4,5], fill_value=0)
    )
    st.dataframe(matriz, use_container_width=True)

    st.markdown("---")
    st.subheader("📤 Exportações & Backup")
    colx1, colx2 = st.columns(2)
    if colx1.download_button("Baixar riscos (Excel)", data=_to_excel_bytes(df_view), file_name="riscos_export.xlsx"):
        st.toast("Exportação gerada.")
    if colx2.button("Exportar backup manual"):
        storage.backup(df_riscos, prefix='riscos')
        st.success("Backup enviado.")

    st.info(
        "Dica: use severidade (probabilidade x impacto) para priorizar. "
        "Defina estratégia e prazos claros no plano de mitigação. Associe riscos ao projeto para aparecerem na visão executiva.")


# -----------------------------
# Integração com roteador do App principal
# -----------------------------

def registrar_pagina(router: dict):
    router["🚩 Riscos"] = aba_cadastro_riscos

# Compatibilidade com import legado:
# allow: from modules.cadastro_riscos import cadastro_riscos

def cadastro_riscos():
    return aba_cadastro_riscos()


if __name__ == "__main__":
    aba_cadastro_riscos()
