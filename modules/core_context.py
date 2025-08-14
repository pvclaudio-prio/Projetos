import streamlit as st
import pandas as pd
from typing import List, Tuple, Optional
from modules.crud_utils import carregar_arquivo_excel

BASE_ATV = "bases/projetos_atividades.xlsx"
SHEET_ATV = "projetos_atividades"

# ──────────────────────────────────────────────────────────────────────────────
# Loading & lists

@st.cache_data(show_spinner=False)
def load_df_atividades() -> pd.DataFrame:
    """Carrega a base de Projetos e Atividades e normaliza colunas-chave."""
    try:
        df = carregar_arquivo_excel(BASE_ATV, sheet_name=SHEET_ATV)
        if df is None:
            df = pd.DataFrame()
    except Exception:
        df = pd.DataFrame()

    # Garante colunas mínimas
    for c in ["id", "projeto", "atividade", "inicio", "fim", "status", "prioridade", "responsavel"]:
        if c not in df.columns:
            df[c] = ""

    # Normalizações
    for c in ["projeto", "atividade", "responsavel", "status", "prioridade", "id"]:
        df[c] = df[c].fillna("").astype(str)

    return df


def list_projetos(df_atv: pd.DataFrame) -> List[str]:
    if df_atv.empty:
        return []
    vals = df_atv["projeto"].dropna().astype(str).str.strip()
    return sorted([p for p in vals.unique().tolist() if p])


def list_atividades(df_atv: pd.DataFrame, projeto: str) -> List[str]:
    if df_atv.empty or not projeto:
        return []
    dff = df_atv[df_atv["projeto"] == projeto]
    if dff.empty:
        return []
    vals = dff["atividade"].dropna().astype(str).str.strip()
    return sorted([a for a in vals.unique().tolist() if a])


# ──────────────────────────────────────────────────────────────────────────────
# Session-state helpers

def _ensure_ctx_defaults(df_atv: pd.DataFrame) -> None:
    """Garante chaves no session_state e reseta se forem inválidas."""
    if "ctx_projeto" not in st.session_state:
        st.session_state["ctx_projeto"] = ""
    if "ctx_atividade" not in st.session_state:
        st.session_state["ctx_atividade"] = ""

    projetos = list_projetos(df_atv)
    if st.session_state["ctx_projeto"] and st.session_state["ctx_projeto"] not in projetos:
        st.session_state["ctx_projeto"] = ""
        st.session_state["ctx_atividade"] = ""

    if st.session_state["ctx_projeto"]:
        atividades = list_atividades(df_atv, st.session_state["ctx_projeto"])
        if st.session_state["ctx_atividade"] and st.session_state["ctx_atividade"] not in atividades:
            st.session_state["ctx_atividade"] = ""


# ──────────────────────────────────────────────────────────────────────────────
# Public API

def seletor_contexto(show_atividade: bool = True, obrigatorio: bool = True) -> None:
    """
    Desenha o seletor fixo de Projeto (obrigatório) e Atividade (opcional).
    Salva em st.session_state["ctx_projeto"] / ["ctx_atividade"].
    """
    df_atv = load_df_atividades()
    _ensure_ctx_defaults(df_atv)

    projetos = list_projetos(df_atv)
    st.markdown("### 📌 Contexto do Projeto")

    c1, c2 = st.columns([2, 2])
    with c1:
        opts_proj = [""] + projetos
        idx_proj = opts_proj.index(st.session_state["ctx_projeto"]) if st.session_state["ctx_projeto"] in opts_proj else 0
        st.session_state["ctx_projeto"] = st.selectbox(
            "Projeto", options=opts_proj, index=idx_proj,
            help="Escolha um projeto já cadastrado em 🗂️ Projetos e Atividades."
        )

    with c2:
        if show_atividade and st.session_state["ctx_projeto"]:
            atividades = list_atividades(df_atv, st.session_state["ctx_projeto"])
            opts_ativ = [""] + atividades
            idx_ativ = opts_ativ.index(st.session_state["ctx_atividade"]) if st.session_state["ctx_atividade"] in opts_ativ else 0
            st.session_state["ctx_atividade"] = st.selectbox(
                "Atividade (opcional)", options=opts_ativ, index=idx_ativ,
                help="(Opcional) Filtra itens da aba para uma atividade específica."
            )
        else:
            st.session_state["ctx_atividade"] = ""

    if obrigatorio and not st.session_state["ctx_projeto"]:
        st.warning("Selecione um **Projeto** para continuar.")
        st.stop()


def validar_projeto_atividade_valido(projeto: str, atividade: Optional[str] = None) -> Tuple[bool, str]:
    """Valida se o projeto (e opcionalmente a atividade) existem no cadastro oficial."""
    df = load_df_atividades()
    if not projeto:
        return False, "Projeto não informado."
    if df.empty:
        return False, "Não há projetos cadastrados em 🗂️ Projetos e Atividades."

    if projeto not in list_projetos(df):
        return False, f"O projeto '{projeto}' não existe. Cadastre antes em 🗂️ Projetos e Atividades."

    if atividade:
        if atividade not in list_atividades(df, projeto):
            return False, f"A atividade '{atividade}' não existe no projeto '{projeto}'."
    return True, ""
