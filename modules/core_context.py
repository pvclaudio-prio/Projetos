import streamlit as st
import pandas as pd
from datetime import date

from modules.crud_utils import carregar_arquivo_excel

BASE_ATV = "bases/projetos_atividades.xlsx"
SHEET_ATV = "projetos_atividades"

@st.cache_data(show_spinner=False)
def load_df_atividades() -> pd.DataFrame:
    try:
        df = carregar_arquivo_excel(BASE_ATV, sheet_name=SHEET_ATV)
        if df is None:
            return pd.DataFrame(columns=["id","projeto","atividade","inicio","fim","status","prioridade","responsavel"])
        # normalizações mínimas
        for c in ["projeto","atividade","responsavel","status","prioridade"]:
            if c not in df.columns:
                df[c] = ""
            else:
                df[c] = df[c].fillna("").astype(str)
        if "id" not in df.columns:
            df["id"] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=["id","projeto","atividade","inicio","fim","status","prioridade","responsavel"])

def list_projetos(df_atv: pd.DataFrame) -> list[str]:
    if df_atv.empty: return []
    return sorted([p for p in df_atv["projeto"].dropna().astype(str).unique() if p.strip()])

def list_atividades(df_atv: pd.DataFrame, projeto: str) -> list[str]:
    if df_atv.empty or not projeto: return []
    dff = df_atv[df_atv["projeto"] == projeto]
    if dff.empty: return []
    return sorted([a for a in dff["atividade"].dropna().astype(str).unique() if a.strip()])

def ensure_ctx_defaults(df_atv: pd.DataFrame):
    # Garante que existam ctx_projeto e ctx_atividade válidos
    if "ctx_projeto" not in st.session_state: st.session_state["ctx_projeto"] = ""
    if "ctx_atividade" not in st.session_state: st.session_state["ctx_atividade"] = ""

    projetos = list_projetos(df_atv)
    if st.session_state["ctx_projeto"] and st.session_state["ctx_projeto"] not in projetos:
        st.session_state["ctx_projeto"] = ""
        st.session_state["ctx_atividade"] = ""
    if st.session_state["ctx_projeto"]:
        atividades = list_atividades(df_atv, st.session_state["ctx_projeto"])
        if st.session_state["ctx_atividade"] and st.session_state["ctx_atividade"] not in atividades:
            st.session_state["ctx_atividade"] = ""

def seletor_contexto(show_atividade: bool = True, obrigatorio: bool = True):
    """
    Renderiza o seletor padrão no topo das abas:
    - selectbox de Projeto (obrigatório)
    - selectbox de Atividade (opcional, dependente do projeto)
    Guarda escolhas em st.session_state["ctx_projeto"] / ["ctx_atividade"]
    """
    df_atv = load_df_atividades()
    ensure_ctx_defaults(df_atv)
    projetos = list_projetos(df_atv)

    st.markdown("### 📌 Contexto do Projeto")
    c1, c2 = st.columns([2, 2])
    with c1:
        st.session_state["ctx_projeto"] = st.selectbox(
            "Projeto",
            options=[""] + projetos,
            index=([""] + projetos).index(st.session_state["ctx_projeto"]) if st.session_state["ctx_projeto"] in ([""] + projetos) else 0,
            help="Escolha um projeto já cadastrado em 🗂️ Projetos e Atividades."
        )
    with c2:
        if show_atividade and st.session_state["ctx_projeto"]:
            atividades = list_atividades(df_atv, st.session_state["ctx_projeto"])
            st.session_state["ctx_atividade"] = st.selectbox(
                "Atividade (opcional)",
                options=[""] + atividades,
                index=([""] + atividades).index(st.session_state["ctx_atividade"]) if st.session_state["ctx_atividade"] in ([""] + atividades) else 0,
                help="Filtra itens da aba atual para uma atividade específica."
            )
        else:
            st.session_state["ctx_atividade"] = ""

    # Alerta se obrigatório e vazio
    if obrigatorio and not st.session_state["ctx_projeto"]:
        st.warning("Selecione um **Projeto** para continuar.")
        st.stop()

def validar_projeto_atividade_valido(projeto: str, atividade: str | None = None) -> tuple[bool, str]:
    df = load_df_atividades()
    if not projeto or df.empty:
        return False, "Projeto não informado ou não há projetos cadastrados."
    if projeto not in list_projetos(df):
        return False, f"O projeto '{projeto}' não existe. Cadastre antes em 🗂️ Projetos e Atividades."
    if atividade:
        if atividade not in list_atividades(df, projeto):
            return False, f"A atividade '{atividade}' não existe no projeto '{projeto}'."
    return True, ""
