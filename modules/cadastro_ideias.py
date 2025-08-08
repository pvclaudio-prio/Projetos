import streamlit as st
import pandas as pd
from datetime import date
import uuid
import plotly.express as px
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

ARQUIVO_IDEIAS = "ideias.xlsx"

def _gerar_id():
    return str(uuid.uuid4())

def _prioridade(impacto: float, esforco: float) -> float:
    # Métrica simples e efetiva para priorização
    return round(float(impacto) / (float(esforco) + 0.5), 3)

def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    # Garante colunas base mesmo se arquivo estiver vazio/novo
    colunas = [
        "ID", "Responsável", "Descrição", "Plano de Ação",
        "Prazo", "Impacto (1-5)", "Esforço (1-5)", "Prioridade"
    ]
    for c in colunas:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    # Tipos
    if not df.empty:
        if "Prazo" in df.columns:
            df["Prazo"] = pd.to_datetime(df["Prazo"], errors="coerce").dt.date
        for c in ["Impacto (1-5)", "Esforço (1-5)", "Prioridade"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[colunas]

def _carregar_base() -> pd.DataFrame:
    df = carregar_arquivo_excel(ARQUIVO_IDEIAS)
    if df is None or df.empty:
        df = pd.DataFrame(columns=[
            "ID", "Responsável", "Descrição", "Plano de Ação",
            "Prazo", "Impacto (1-5)", "Esforço (1-5)", "Prioridade"
        ])
    return _padronizar_colunas(df)

def _salvar_base(df: pd.DataFrame):
    df = _padronizar_colunas(df)
    salvar_arquivo_excel(df, ARQUIVO_IDEIAS)

def cadastro_ideias():
    st.header("💡 Cadastro de Ideias & Matriz de Priorização")

    # ========================
    # FORMULÁRIO DE CADASTRO
    # ========================
    with st.form("form_ideia"):
        col1, col2 = st.columns([2, 2])
        with col1:
            responsavel = st.text_input("Responsável")
            prazo = st.date_input("Prazo para implementação", value=date.today())
        with col2:
            impacto = st.slider("Impacto (1 = baixo, 5 = alto)", min_value=1, max_value=5, value=3)
            esforco = st.slider("Esforço (1 = baixo, 5 = alto)", min_value=1, max_value=5, value=3)

        descricao = st.text_area("Descrição da Ideia")
        plano_acao = st.text_area("Plano de Ação (passo a passo)")

        submitted = st.form_submit_button("💾 Cadastrar Ideia")
        if submitted:
            if not responsavel or not descricao:
                st.warning("⚠️ Responsável e Descrição são obrigatórios.")
            else:
                df = _carregar_base()
                novo = pd.DataFrame([{
                    "ID": _gerar_id(),
                    "Responsável": responsavel.strip(),
                    "Descrição": descricao.strip(),
                    "Plano de Ação": plano_acao.strip(),
                    "Prazo": prazo,
                    "Impacto (1-5)": int(impacto),
                    "Esforço (1-5)": int(esforco),
                    "Prioridade": _prioridade(impacto, esforco)
                }])
