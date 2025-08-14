# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import date
from common import load_base, save_base, _parse_date

def aba_riscos(st):
    st.subheader("⚠️ Riscos do Projeto")

    df_proj = load_base("projetos")
    if df_proj.empty:
        st.warning("Cadastre primeiro um projeto na aba Projetos.")
        return

    df_riscos = load_base("riscos")

    proj_nome = st.selectbox("Projeto", df_proj["nome_projeto"].tolist())
    projeto_id = df_proj.loc[df_proj["nome_projeto"] == proj_nome, "id"].iloc[0]

    st.write("### Adicionar novo risco")
    with st.form("form_risco"):
        categoria = st.text_input("Categoria do risco")
        descricao = st.text_area("Descrição do risco")
        severidade = st.selectbox("Severidade", ["Baixo", "Médio", "Alto", "Crítico"])
        probabilidade = st.selectbox("Probabilidade", ["Remota", "Possível", "Provável", "Quase certa"])
        status_tratativa = st.selectbox("Status da tratativa", ["Aberto", "Em tratamento", "Mitigando", "Fechado"])
        responsavel = st.text_input("Responsável")
        prazo_tratativa = st.date_input("Prazo para tratativa", value=date.today())
        impacto_financeiro = st.number_input("Impacto financeiro (BRL)", min_value=0.0, step=1000.0, format="%.2f")

        submit = st.form_submit_button("Salvar risco")

    if submit:
        novo_risco = {
            "projeto_id": projeto_id,
            "categoria": categoria,
            "descricao": descricao,
            "severidade": severidade,
            "probabilidade": probabilidade,
            "status_tratativa": status_tratativa,
            "responsavel": responsavel,
            "prazo_tratativa": prazo_tratativa,
            "impacto_financeiro": impacto_financeiro,
        }
        df_riscos = pd.concat([df_riscos, pd.DataFrame([novo_risco])], ignore_index=True)
        save_base("riscos", df_riscos)
        st.success("Risco salvo com sucesso!")

    st.write("### Riscos cadastrados")
    df_riscos_proj = df_riscos[df_riscos.get("projeto_id", "") == projeto_id].copy()

    if df_riscos_proj.empty:
        st.caption("Nenhum risco cadastrado.")
    else:
        # Ordena pelo prazo e severidade para priorizar
        df_riscos_proj["prazo_tratativa"] = df_riscos_proj["prazo_tratativa"].apply(_parse_date)
        st.dataframe(
            df_riscos_proj.sort_values(["prazo_tratativa", "severidade"], ascending=[True, False]),
            use_container_width=True
        )
