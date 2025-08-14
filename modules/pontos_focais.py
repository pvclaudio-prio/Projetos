import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

BASE_CONTATOS = "bases/projetos_contatos.xlsx"
SHEET_CONTATOS = "contatos"

COLS = [
    "id", "projeto", "empresa", "nome", "cargo", "email", "telefone",
    "responsavel_por", "observacoes", "criado_em", "atualizado_em"
]
EMPRESAS = ["Contratada", "PRIO"]

@st.cache_data(show_spinner=False)
def _load_contatos() -> pd.DataFrame:
    try:
        df = carregar_arquivo_excel(BASE_CONTATOS, sheet_name=SHEET_CONTATOS)
        if df is None or df.empty:
            df = pd.DataFrame(columns=COLS)
    except Exception:
        df = pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in df.columns:
            df[c] = None
    for c in ["projeto","empresa","nome","cargo","email","telefone","responsavel_por","observacoes"]:
        df[c] = df[c].fillna("").astype(str)
    return df[COLS].copy()


def _save_contatos(df: pd.DataFrame):
    df = df[COLS].copy()
    salvar_arquivo_excel(df, BASE_CONTATOS, sheet_name=SHEET_CONTATOS)
    _load_contatos.clear()


def aba_pontos_focais(usuario_logado: str, nome_usuario: str):
    st.title("👥 Pontos Focais dos Projetos")

    df = _load_contatos()

    # Filtro automático vindo da seleção da aba Projetos e Atividades
    projeto_filtro = st.session_state.get("projeto_selecionado")
    if projeto_filtro:
        st.info(f"Filtrando contatos para o projeto: **{projeto_filtro}**")
        df = df[df["projeto"] == projeto_filtro].copy()
        if st.button("Limpar filtro de projeto"):
            st.session_state.pop("projeto_selecionado", None)
            st.rerun()

    st.subheader("Contatos Cadastrados")
    st.dataframe(df[["projeto","empresa","nome","cargo","email","telefone","responsavel_por"]].sort_values(["projeto","empresa","nome"]).reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("➕ Novo Contato")
    with st.form("form_contato"):
        col1, col2 = st.columns(2)
        projeto = col1.text_input("Projeto", placeholder="Ex.: Integração Teradata")
        empresa = col2.selectbox("Empresa", EMPRESAS)

        col3, col4, col5 = st.columns(3)
        nome = col3.text_input("Nome")
        cargo = col4.text_input("Cargo")
        email = col5.text_input("E-mail")

        col6, col7 = st.columns(2)
        telefone = col6.text_input("Telefone")
        responsavel_por = col7.text_input("Responsável por (escopo)", placeholder="Ex.: Gestão do contrato, Integração SAP, etc.")

        observacoes = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar contato")

    if submitted:
        if not projeto.strip() or not nome.strip():
            st.error("Informe ao menos Projeto e Nome.")
        else:
            novo = {
                "id": str(uuid.uuid4()), "projeto": projeto.strip(), "empresa": empresa,
                "nome": nome.strip(), "cargo": cargo.strip(), "email": email.strip(), "telefone": telefone.strip(),
                "responsavel_por": responsavel_por.strip(), "observacoes": observacoes.strip(),
                "criado_em": datetime.now().isoformat(timespec="seconds"), "atualizado_em": datetime.now().isoformat(timespec="seconds")
            }
            df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
            _save_contatos(df)
            st.success("Contato salvo.")
            st.rerun()

    with st.expander("✏️ Editar / 🗑️ Excluir"):
        if not df.empty:
            ids = st.multiselect("Selecione IDs", df["id"].tolist())
            colE1, colE2 = st.columns(2)
            if colE1.button("Excluir selecionados", disabled=not ids):
                df = df[~df["id"].isin(ids)].copy()
                _save_contatos(df)
                st.success("Excluídos.")
                st.rerun()
            if colE2.button("Limpar tudo (cuidado)"):
                _save_contatos(pd.DataFrame(columns=COLS))
                st.success("Base de contatos limpa.")
                st.rerun()
