import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel
from modules.core_context import (
    seletor_contexto,
    validar_projeto_atividade_valido,
    load_df_atividades,
    list_projetos,
)

BASE_CONTATOS = "bases/projetos_contatos.xlsx"
SHEET_CONTATOS = "contatos"

COLS = [
    "id", "projeto", "empresa", "nome", "cargo", "email", "telefone",
    "responsavel_por", "observacoes", "criado_em", "atualizado_em"
]
EMPRESAS = ["Contratada", "PRIO"]

# ──────────────────────────────────────────────────────────────────────────────
# I/O

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

# ──────────────────────────────────────────────────────────────────────────────
# UI

def aba_pontos_focais(usuario_logado: str, nome_usuario: str):
    st.title("👥 Pontos Focais dos Projetos")

    # 🔗 Vincula ao cadastro oficial (projeto obrigatório)
    seletor_contexto(show_atividade=False, obrigatorio=True)
    projeto_ctx = st.session_state["ctx_projeto"]

    df = _load_contatos()

    # Lista somente contatos do projeto selecionado
    df_proj = df[df["projeto"] == projeto_ctx].copy()

    st.subheader(f"Contatos do Projeto: **{projeto_ctx}**")
    if df_proj.empty:
        st.caption("Nenhum contato cadastrado ainda para este projeto.")
    else:
        st.dataframe(
            df_proj[["empresa","nome","cargo","email","telefone","responsavel_por","observacoes"]]
            .sort_values(["empresa","nome"])
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
    st.subheader("➕ Novo Contato")
    with st.form("form_contato"):
        st.caption(f"Projeto: **{projeto_ctx}** (definido no seletor do topo)")
        col1, col2 = st.columns(2)
        empresa = col1.selectbox("Empresa", EMPRESAS)
        nome = col2.text_input("Nome")

        col3, col4, col5 = st.columns(3)
        cargo = col3.text_input("Cargo")
        email = col4.text_input("E-mail")
        telefone = col5.text_input("Telefone")

        col6, col7 = st.columns(2)
        responsavel_por = col6.text_input("Responsável por (escopo)", placeholder="Ex.: Gestão do contrato, Integração SAP")
        observacoes = col7.text_input("Observações (opcional)")

        submitted = st.form_submit_button("Salvar contato")

    if submitted:
        projeto = projeto_ctx  # sempre o contexto atual
        ok, msg = validar_projeto_atividade_valido(projeto)
        if not ok:
            st.error(msg)
            st.stop()
        if not nome.strip():
            st.error("Informe o nome do contato.")
            st.stop()

        novo = {
            "id": str(uuid.uuid4()), "projeto": projeto, "empresa": empresa,
            "nome": nome.strip(), "cargo": cargo.strip(), "email": email.strip(), "telefone": telefone.strip(),
            "responsavel_por": responsavel_por.strip(), "observacoes": observacoes.strip(),
            "criado_em": datetime.now().isoformat(timespec="seconds"),
            "atualizado_em": datetime.now().isoformat(timespec="seconds")
        }
        df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
        _save_contatos(df)
        st.success("Contato salvo.")
        st.rerun()

    with st.expander("✏️ Editar / 🗑️ Excluir"):
        df_proj = _load_contatos()
        df_proj = df_proj[df_proj["projeto"] == projeto_ctx].copy()
        if df_proj.empty:
            st.caption("Nenhum contato deste projeto para editar/excluir.")
        else:
            ids = st.multiselect(
                "Selecione IDs",
                df_proj["id"].tolist(),
                format_func=lambda _id: f"{_id} — {df_proj.loc[df_proj['id']==_id, 'nome'].values[0] if (df_proj['id']==_id).any() else _id}"
            )

            # Edição do primeiro selecionado
            if ids:
                sel_id = ids[0]
                reg = df_proj.loc[df_proj["id"] == sel_id].iloc[0].to_dict()
                st.write(f"Editando ID: **{sel_id}**")
                with st.form("form_editar"):
                    col1, col2 = st.columns(2)
                    empresa_e = col1.selectbox("Empresa", EMPRESAS, index=EMPRESAS.index(reg.get("empresa","PRIO")) if reg.get("empresa","PRIO") in EMPRESAS else 1)
                    nome_e = col2.text_input("Nome", value=reg.get("nome",""))

                    col3, col4, col5 = st.columns(3)
                    cargo_e = col3.text_input("Cargo", value=reg.get("cargo",""))
                    email_e = col4.text_input("E-mail", value=reg.get("email",""))
                    telefone_e = col5.text_input("Telefone", value=reg.get("telefone",""))

                    col6, col7 = st.columns(2)
                    resp_e = col6.text_input("Responsável por (escopo)", value=reg.get("responsavel_por",""))
                    obs_e = col7.text_input("Observações (opcional)", value=reg.get("observacoes",""))

                    sub_edit = st.form_submit_button("Salvar alterações")

                if sub_edit:
                    df_all = _load_contatos()
                    df_all.loc[df_all["id"] == sel_id, [
                        "empresa","nome","cargo","email","telefone","responsavel_por","observacoes","atualizado_em"
                    ]] = [
                        empresa_e, nome_e.strip(), cargo_e.strip(), email_e.strip(), telefone_e.strip(),
                        resp_e.strip(), obs_e.strip(), datetime.now().isoformat(timespec="seconds")
                    ]
                    _save_contatos(df_all)
                    st.success("Contato atualizado.")
                    st.rerun()

            colE1, colE2 = st.columns(2)
            if colE1.button("Excluir selecionados", disabled=not ids):
                df_all = _load_contatos()
                df_all = df_all[~df_all["id"].isin(ids)].copy()
                _save_contatos(df_all)
                st.success("Excluídos.")
                st.rerun()
            if colE2.button("Limpar todos os contatos do projeto (cuidado)"):
                df_all = _load_contatos()
                df_all = df_all[df_all["projeto"] != projeto_ctx].copy()
                _save_contatos(df_all)
                st.success("Base de contatos do projeto limpa.")
                st.rerun()
