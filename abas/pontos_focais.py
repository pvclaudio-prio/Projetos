# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
import pandas as pd
import streamlit as st
from common import load_base, save_base, _now_iso

def aba_pontos_focais(st):
    st.subheader("👥 Pontos Focais do Projeto")
    st.caption("Cadastre stakeholders e contatos principais por projeto.")

    df_p = load_base("projetos").copy()
    df_pf = load_base("pontos_focais").copy()

    if df_p.empty:
        st.info("Cadastre um projeto na aba 'Projetos & Escopo' antes de incluir pontos focais.")
        return

    # ---------- Novo ponto focal ----------
    with st.expander("➕ Novo ponto focal", expanded=False):
        proj_idx = st.selectbox(
            "Projeto",
            options=list(range(len(df_p))),
            format_func=lambda i: df_p.loc[i, "nome_projeto"],
            key="pf_proj",
        )
        nome = st.text_input("Nome", key="pf_nome")
        email = st.text_input("E-mail", key="pf_email")
        telefone = st.text_input("Telefone", key="pf_tel")
        funcao = st.text_input("Função / Papel", key="pf_func")
        observ = st.text_area("Observações", key="pf_obs")

        if st.button("Salvar ponto focal", type="primary", key="pf_salvar"):
            novo = {
                "id": str(uuid.uuid4()),
                "projeto_id": df_p.loc[proj_idx, "id"],
                "nome": nome.strip(),
                "email": email.strip(),
                "telefone": telefone.strip(),
                "funcao": funcao.strip(),
                "observacoes": observ.strip(),
                "criado_em": _now_iso(),
                "atualizado_em": _now_iso(),
            }
            df_pf = pd.concat([df_pf, pd.DataFrame([novo])], ignore_index=True)
            save_base(df_pf, "pontos_focais")
            st.success("Ponto focal salvo.")

    if df_pf.empty:
        st.info("Nenhum ponto focal cadastrado.")
        return

    # ---------- Lista ----------
    df_pfx = df_pf.merge(
        df_p[["id", "nome_projeto"]],
        left_on="projeto_id",
        right_on="id",
        how="left",
    ).rename(columns={"nome_projeto": "Projeto"})

    st.write("### Pontos focais")
    st.dataframe(
        df_pfx[["Projeto", "nome", "email", "telefone", "funcao", "observacoes"]]
        .rename(columns={
            "nome": "Nome", "email": "E-mail", "telefone": "Telefone",
            "funcao": "Função", "observacoes": "Observações"
        })
        .sort_values(["Projeto", "Nome"]),
        use_container_width=True,
    )

    # ---------- Edição ----------
    id_col = "id_x" if "id_x" in df_pfx.columns else "id"
    id_map = df_pfx[id_col].tolist()
    if id_map:
        idx = st.selectbox(
            "Selecione um ponto focal",
            options=list(range(len(id_map))),
            format_func=lambda i: f"{df_pfx.iloc[i]['Projeto']} · {df_pfx.iloc[i]['nome']}",
            key="ed_pf_idx",
        )
        if idx is not None:
            pf_id = id_map[idx]
            df_pf = load_base("pontos_focais").copy()
            row = df_pf[df_pf["id"] == pf_id].iloc[0]

            nome_e = st.text_input("Nome", value=row["nome"], key="ed_pf_nome")
            email_e = st.text_input("E-mail", value=row.get("email", ""), key="ed_pf_email")
            tel_e = st.text_input("Telefone", value=row.get("telefone", ""), key="ed_pf_tel")
            func_e = st.text_input("Função", value=row.get("funcao", ""), key="ed_pf_func")
            obs_e = st.text_area("Observações", value=row.get("observacoes", ""), key="ed_pf_obs")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Salvar alterações", key="ed_pf_salvar"):
                    df_pf.loc[df_pf["id"] == pf_id, [
                        "nome", "email", "telefone", "funcao", "observacoes", "atualizado_em"
                    ]] = [
                        nome_e.strip(), email_e.strip(), tel_e.strip(), func_e.strip(), obs_e.strip(), _now_iso()
                    ]
                    save_base(df_pf, "pontos_focais")
                    st.success("Ponto focal atualizado.")
            with c2:
                if st.button("Excluir ponto focal", key="ed_pf_excluir"):
                    df_pf = df_pf[df_pf["id"] != pf_id].reset_index(drop=True)
                    save_base(df_pf, "pontos_focais")
                    st.warning("Ponto focal excluído.")

