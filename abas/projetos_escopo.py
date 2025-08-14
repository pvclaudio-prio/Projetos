# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
import pandas as pd
import streamlit as st
from common import load_base, save_base, _now_iso

def aba_projetos_escopo(st):
    st.subheader("📁 Projetos & Escopo")
    st.caption("Cadastre seus projetos e detalhe o escopo no campo abaixo.")

    df_p = load_base("projetos").copy()

    # ---------- Novo projeto ----------
    with st.expander("➕ Novo projeto", expanded=False):
        nome = st.text_input("Nome do projeto", key="np_nome")
        escopo = st.text_area(
            "Escopo do projeto",
            key="np_escopo",
            height=160,
            help="Descreva objetivos, entregáveis, premissas e restrições.",
        )
        if st.button("Salvar projeto", type="primary", key="np_salvar"):
            if not nome.strip():
                st.error("Informe o nome do projeto.")
            else:
                novo = {
                    "id": str(uuid.uuid4()),
                    "nome_projeto": nome.strip(),
                    "escopo": escopo.strip(),
                    "criado_em": _now_iso(),
                    "atualizado_em": _now_iso(),
                }
                df_p = pd.concat([df_p, pd.DataFrame([novo])], ignore_index=True)
                save_base(df_p, "projetos")
                st.success("Projeto salvo com sucesso.")

    if df_p.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # ---------- Lista ----------
    st.write("### Projetos")
    st.dataframe(
        df_p[["nome_projeto", "escopo", "criado_em"]]
        .rename(columns={"nome_projeto": "Projeto", "escopo": "Escopo"}),
        use_container_width=True,
    )

    # ---------- Edição ----------
    st.write("### Editar projeto")
    proj_idx = st.selectbox(
        "Selecione um projeto para editar",
        options=list(range(len(df_p))),
        format_func=lambda i: df_p.loc[i, "nome_projeto"],
        key="ed_proj_idx",
    )

    if proj_idx is None:
        return

    nome_e = st.text_input(
        "Nome do projeto", value=df_p.loc[proj_idx, "nome_projeto"], key="ed_nome"
    )
    escopo_e = st.text_area(
        "Escopo do projeto", value=df_p.loc[proj_idx, "escopo"], height=160, key="ed_escopo"
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Salvar alterações", key="ed_salvar"):
            df_p.loc[proj_idx, "nome_projeto"] = nome_e.strip()
            df_p.loc[proj_idx, "escopo"] = escopo_e.strip()
            df_p.loc[proj_idx, "atualizado_em"] = _now_iso()
            save_base(df_p, "projetos")
            st.success("Projeto atualizado.")
    with c2:
        if st.button("Excluir projeto", key="ed_excluir"):
            pid = df_p.loc[proj_idx, "id"]
            # Remove o projeto
            df_p = df_p.drop(index=proj_idx).reset_index(drop=True)
            save_base(df_p, "projetos")

            # Cascata nas demais bases
            for nome_base in ("atividades", "financeiro", "pontos_focais", "riscos"):
                df = load_base(nome_base)
                if not df.empty and "projeto_id" in df.columns:
                    df = df[df["projeto_id"] != pid].reset_index(drop=True)
                    save_base(df, nome_base)

            st.warning("Projeto excluído e registros vinculados removidos.")

