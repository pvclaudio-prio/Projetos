# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
import pandas as pd
import streamlit as st
from common import load_base, save_base, _now_iso

def aba_riscos(st):
    st.subheader("⚠️ Riscos do Projeto")
    st.caption("Mapeie, avalie e acompanhe riscos por projeto.")

    df_p = load_base("projetos").copy()
    df_r = load_base("riscos").copy()

    if df_p.empty:
        st.info("Cadastre um projeto na aba 'Projetos & Escopo' antes de incluir riscos.")
        return

    # ---------- Novo risco ----------
    with st.expander("➕ Novo risco", expanded=False):
        proj_idx = st.selectbox(
            "Projeto",
            options=list(range(len(df_p))),
            format_func=lambda i: df_p.loc[i, "nome_projeto"],
            key="rk_proj",
        )
        titulo = st.text_input("Título do risco", key="rk_titulo")
        descricao = st.text_area("Descrição detalhada", key="rk_desc")
        prob = st.selectbox("Probabilidade", ["Baixa", "Média", "Alta"], key="rk_prob")
        impacto = st.selectbox("Impacto", ["Baixo", "Médio", "Alto"], key="rk_impacto")
        plano_mitig = st.text_area("Plano de mitigação", key="rk_mitig")
        responsavel = st.text_input("Responsável", key="rk_resp")
        status = st.selectbox("Status", ["Aberto", "Mitigando", "Encerrado"], key="rk_status")

        if st.button("Salvar risco", type="primary", key="rk_salvar"):
            novo = {
                "id": str(uuid.uuid4()),
                "projeto_id": df_p.loc[proj_idx, "id"],
                "titulo": titulo.strip(),
                "descricao": descricao.strip(),
                "probabilidade": prob,
                "impacto": impacto,
                "plano_mitigacao": plano_mitig.strip(),
                "responsavel": responsavel.strip(),
                "status": status,
                "criado_em": _now_iso(),
                "atualizado_em": _now_iso(),
            }
            df_r = pd.concat([df_r, pd.DataFrame([novo])], ignore_index=True)
            save_base(df_r, "riscos")
            st.success("Risco salvo.")

    if df_r.empty:
        st.info("Nenhum risco cadastrado.")
        return

    # ---------- Lista ----------
    df_rx = df_r.merge(
        df_p[["id", "nome_projeto"]],
        left_on="projeto_id",
        right_on="id",
        how="left",
    ).rename(columns={"nome_projeto": "Projeto"})

    st.write("### Riscos mapeados")
    st.dataframe(
        df_rx[["Projeto", "titulo", "probabilidade", "impacto", "status", "responsavel", "plano_mitigacao"]]
        .rename(columns={
            "titulo": "Título",
            "probabilidade": "Prob.",
            "impacto": "Impacto",
            "status": "Status",
            "responsavel": "Responsável",
            "plano_mitigacao": "Plano de Mitigação"
        }),
        use_container_width=True,
    )

    # ---------- Edição ----------
    id_col = "id_x" if "id_x" in df_rx.columns else "id"
    id_map = df_rx[id_col].tolist()
    if id_map:
        idx = st.selectbox(
            "Selecione um risco",
            options=list(range(len(id_map))),
            format_func=lambda i: f"{df_rx.iloc[i]['Projeto']} · {df_rx.iloc[i]['titulo']}",
            key="ed_rk_idx",
        )
        if idx is not None:
            rk_id = id_map[idx]
            df_r = load_base("riscos").copy()
            row = df_r[df_r["id"] == rk_id].iloc[0]

            titulo_e = st.text_input("Título", value=row["titulo"], key="ed_rk_titulo")
            desc_e = st.text_area("Descrição", value=row["descricao"], key="ed_rk_desc")
            prob_e = st.selectbox("Probabilidade", ["Baixa", "Média", "Alta"], index=["Baixa","Média","Alta"].index(row["probabilidade"]), key="ed_rk_prob")
            impacto_e = st.selectbox("Impacto", ["Baixo", "Médio", "Alto"], index=["Baixo","Médio","Alto"].index(row["impacto"]), key="ed_rk_impacto")
            plano_e = st.text_area("Plano de mitigação", value=row["plano_mitigacao"], key="ed_rk_plano")
            resp_e = st.text_input("Responsável", value=row["responsavel"], key="ed_rk_resp")
            status_e = st.selectbox("Status", ["Aberto", "Mitigando", "Encerrado"], index=["Aberto","Mitigando","Encerrado"].index(row["status"]), key="ed_rk_status")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Salvar alterações", key="ed_rk_salvar"):
                    df_r.loc[df_r["id"] == rk_id, [
                        "titulo", "descricao", "probabilidade", "impacto", "plano_mitigacao",
                        "responsavel", "status", "atualizado_em"
                    ]] = [
                        titulo_e.strip(), desc_e.strip(), prob_e, impacto_e, plano_e.strip(),
                        resp_e.strip(), status_e, _now_iso()
                    ]
                    save_base(df_r, "riscos")
                    st.success("Risco atualizado.")
            with c2:
                if st.button("Excluir risco", key="ed_rk_excluir"):
                    df_r = df_r[df_r["id"] != rk_id].reset_index(drop=True)
                    save_base(df_r, "riscos")
                    st.warning("Risco excluído.")

