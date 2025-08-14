# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from common import load_base, _parse_date

def aba_agenda(st):
    st.subheader("🗓️ Agenda de Atividades & Riscos")
    st.caption("Visualize atividades e tratativas de risco por data. Tudo aqui é carregado automaticamente das abas de Cadastro de Atividades e Riscos.")

    df_p = load_base("projetos").copy()
    df_a = load_base("atividades").copy()
    df_r = load_base("riscos").copy()

    if df_a.empty and df_r.empty:
        st.info("Sem atividades ou riscos cadastrados.")
        return

    # ----------------- Atividades (com projeto_id) -----------------
    if not df_a.empty:
        df_atv = df_a.merge(
            df_p[["id", "nome_projeto"]],
            left_on="projeto_id",
            right_on="id",
            how="left"
        )
        df_atv = df_atv.rename(columns={"nome_projeto": "Projeto"})
        df_atv["Prazo"] = df_atv["prazo"].apply(_parse_date)
    else:
        df_atv = pd.DataFrame(columns=["Projeto", "descricao", "responsavel", "status", "Prazo"])

    # ----------------- Riscos (usa prazo_tratativa) -----------------
    if not df_r.empty:
        df_rsk = df_r.merge(
            df_p[["id", "nome_projeto"]],
            left_on="projeto_id",
            right_on="id",
            how="left"
        )
        df_rsk = df_rsk.rename(columns={"nome_projeto": "Projeto"})
        df_rsk["Prazo"] = df_rsk["prazo_tratativa"].apply(_parse_date)
        df_rsk["Título"] = df_rsk["categoria"].fillna("") + ": " + df_rsk["descricao"].fillna("")
    else:
        df_rsk = pd.DataFrame(columns=["Projeto", "Prazo", "Título", "responsavel", "status_tratativa"])

    # ----------------- KPIs rápidas para atividades -----------------
    hoje = date.today()
    if not df_atv.empty:
        aux = df_atv.copy()
        aux["Status_simplificado"] = aux["status"].replace({"Concluída": "Concluída"}).apply(
            lambda s: s if s == "Concluída" else "Aberta"
        )
        total = len(aux)
        vencidas = len(aux[(aux["Status_simplificado"] == "Aberta") & (aux["Prazo"].notna()) & (aux["Prazo"] < hoje)])
        hoje_q = len(aux[(aux["Status_simplificado"] == "Aberta") & (aux["Prazo"] == hoje)])
        futuras = len(aux[(aux["Status_simplificado"] == "Aberta") & (aux["Prazo"].notna()) & (aux["Prazo"] > hoje)])
    else:
        total = vencidas = hoje_q = futuras = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Atividades - Total", total)
    c2.metric("Vencidas", vencidas)
    c3.metric("Vencem hoje", hoje_q)
    c4.metric("Futuras", futuras)

    st.write("### Atividades por data")
    if not df_atv.empty:
        base = df_atv[df_atv["Prazo"].notna()].copy()
        agenda = (
            base.groupby("Prazo")
            .agg({"descricao": "count"})
            .rename(columns={"descricao": "Qtd"})
            .reset_index()
            .sort_values("Prazo")
        )
        st.dataframe(agenda.rename(columns={"Prazo": "Data"}), use_container_width=True)
    else:
        st.caption("Sem atividades com prazo definido.")

    st.write("### Tratativas de risco por data")
    if not df_rsk.empty:
        base_r = df_rsk[df_rsk["Prazo"].notna()].copy()
        agenda_r = base_r.groupby("Prazo").size().reset_index(name="Qtd").sort_values("Prazo")
        st.dataframe(agenda_r.rename(columns={"Prazo": "Data"}), use_container_width=True)
    else:
        st.caption("Sem riscos com prazo de tratativa definido.")

    # ----------------- Detalhes do dia (unificado) -----------------
    dia = st.date_input("Ver detalhes do dia", value=date.today())

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"#### Atividades em {dia.strftime('%d/%m/%Y')}")
        detal = df_atv[df_atv["Prazo"] == dia]
        if detal.empty:
            st.caption("Sem atividades na data.")
        else:
            st.dataframe(
                detal[["Projeto", "descricao", "responsavel", "status", "Prazo"]]
                .rename(columns={"descricao": "Descrição", "responsavel": "Responsável"})
                .sort_values(["status", "Projeto", "Descrição"]),
                use_container_width=True,
            )

    with col2:
        st.write(f"#### Riscos (tratativas) em {dia.strftime('%d/%m/%Y')}")
        detal_r = df_rsk[df_rsk["Prazo"] == dia]
        if detal_r.empty:
            st.caption("Sem tratativas de risco na data.")
        else:
            st.dataframe(
                detal_r[["Projeto", "Título", "responsavel", "status_tratativa", "Prazo"]]
                .rename(columns={"responsavel": "Responsável", "status_tratativa": "Status"})
                .sort_values(["Status", "Projeto", "Título"]),
                use_container_width=True,
            )

