import streamlit as st
import pandas as pd
import uuid
from datetime import date
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

def aba_projetos_atividades(usuario_logado, nome_usuario):
    st.title("🗂️ Cadastro de Projetos e Atividades")

    # Utilidade interna
    def gerar_id_unico():
        return str(uuid.uuid4())

    # ===============================
    # PROJETOS
    # ===============================
    st.header("🏗️ Projetos")

    with st.form("form_projeto"):
        col1, col2 = st.columns([3, 2])
        with col1:
            nome_projeto = st.text_input("Nome do Projeto")
            fornecedor = st.text_input("Fornecedor")
        with col2:
            custo = st.number_input("Custo Estimado (R$)", min_value=0.0, step=1000.0, format="%.2f")
        
        escopo = st.text_area("Escopo do Projeto")
        partes_interessadas = st.text_area("Partes Interessadas")
        entregaveis = st.text_area("Entregáveis")
        col1, col2 = st.columns(2)
        with col1:
            inicio = st.date_input("Data de Início", value=date.today())
        with col2:
            fim = st.date_input("Data de Término", value=date.today())

        submitted = st.form_submit_button("💾 Cadastrar Projeto")
        if submitted:
            if not nome_projeto:
                st.warning("⚠️ O nome do projeto é obrigatório.")
            else:
                df = carregar_arquivo_excel("projetos.xlsx")
                if nome_projeto in df["Nome"].values:
                    st.warning("⚠️ Já existe um projeto com este nome.")
                else:
                    novo = pd.DataFrame({
                        "ID": [gerar_id_unico()],
                        "Nome": [nome_projeto.strip()],
                        "Fornecedor": [fornecedor.strip()],
                        "Escopo": [escopo.strip()],
                        "Partes Interessadas": [partes_interessadas.strip()],
                        "Custo (R$)": [custo],
                        "Data Início": [inicio],
                        "Data Fim": [fim],
                        "Entregáveis": [entregaveis.strip()]
                    })
                    df = pd.concat([df, novo], ignore_index=True)
                    salvar_arquivo_excel(df, "projetos.xlsx")
                    st.success("✅ Projeto cadastrado com sucesso!")
                    st.rerun()

    # Listar projetos
    st.subheader("📋 Projetos Cadastrados")
    df_projetos = carregar_arquivo_excel("projetos.xlsx")
    if not df_projetos.empty:
        st.dataframe(df_projetos, use_container_width=True)
    else:
        st.info("🚩 Nenhum projeto cadastrado.")

    # ===============================
    # ATIVIDADES
    # ===============================
    st.markdown("---")
    st.header("🗒️ Atividades")

    if df_projetos.empty:
        st.warning("⚠️ Cadastre ao menos um projeto para adicionar atividades.")
        st.stop()

    with st.form("form_atividade"):
        descricao = st.text_input("Descrição da Atividade")
        projeto_vinculado = st.selectbox("Projeto Vinculado", df_projetos["Nome"])
        col1, col2 = st.columns(2)
        with col1:
            data_prevista = st.date_input("Data Prevista", value=date.today())
        with col2:
            horas = st.number_input("Horas Previstas", min_value=0.0, step=0.5, format="%.2f")
        
        responsavel = st.text_input("Responsável")
        status = st.selectbox("Status", ["Não Iniciado", "Em Andamento", "Finalizado"])

        submitted = st.form_submit_button("💾 Cadastrar Atividade")
        if submitted:
            if not descricao:
                st.warning("⚠️ A descrição é obrigatória.")
            else:
                df_atividades = carregar_arquivo_excel("atividades.xlsx")
                nova = pd.DataFrame({
                    "ID": [gerar_id_unico()],
                    "Descrição": [descricao.strip()],
                    "Projeto Vinculado": [projeto_vinculado],
                    "Data Prevista": [data_prevista],
                    "Responsável": [responsavel.strip()],
                    "Horas": [horas],
                    "Status": [status]
                })
                df_atividades = pd.concat([df_atividades, nova], ignore_index=True)
                salvar_arquivo_excel(df_atividades, "atividades.xlsx")
                st.success("✅ Atividade cadastrada com sucesso!")
                st.rerun()

    # Listar atividades
    st.subheader("📋 Atividades Cadastradas")
    df_atividades = carregar_arquivo_excel("atividades.xlsx")
    if not df_atividades.empty:
        st.dataframe(df_atividades, use_container_width=True)
    else:
        st.info("🚩 Nenhuma atividade cadastrada.")

