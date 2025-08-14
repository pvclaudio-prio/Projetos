# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
import pandas as pd
from datetime import date
import streamlit as st
from common import load_base, save_base, _now_iso, _parse_date, STATUS_OPCOES

def aba_cadastro_atividades(st):
    st.subheader("✅ Cadastro de Atividades do Projeto")
    st.caption("Registre atividades com prazo, status, descrição e responsável. Integrado à Agenda.")

    df_p = load_base("projetos").copy()
    df_a = load_base("atividades").copy()

    # Precisa ter ao menos um projeto
    if df_p.empty:
        st.info("Cadastre um projeto na aba 'Projetos & Escopo' antes de incluir atividades.")
        return

    # ---------- Nova atividade ----------
    with st.expander("➕ Nova atividade", expanded=False):
        proj_idx = st.selectbox(
            "Projeto",
            options=list(range(len(df_p))),
            format_func=lambda i: df_p.loc[i, "nome_projeto"],
            key="na_proj",
        )
        descricao = st.text_area("Descrição da atividade", key="na_desc")
        prazo = st.date_input("Prazo (vencimento)", key="na_prazo")
        status = st.selectbox("Status", STATUS_OPCOES, index=0, key="na_status")
        responsavel = st.text_input("Responsável", key="na_resp")

        if st.button("Salvar atividade", type="primary", key="na_salvar"):
            if not descricao.strip():
                st.error("Informe a descrição da atividade.")
            else:
                novo = {
                    "id": str(uuid.uuid4()),
                    "projeto_id": df_p.loc[proj_idx, "id"],
                    "descricao": descricao.strip(),
                    "prazo": _parse_date(prazo).strftime("%Y-%m-%d") if prazo else None,
                    "status": status,
                    "responsavel": responsavel.strip(),
                    "criado_em": _now_iso(),
                    "atualizado_em": _now_iso(),
                }
                df_a = pd.concat([df_a, pd.DataFrame([novo])], ignore_index=True)
                save_base(df_a, "atividades")
                st.success("Atividade salva e enviada para a Agenda.")

    if df_a.empty:
        st.info("Nenhuma atividade cadastrada ainda.")
        return

    # ---------- Filtros ----------
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        proj_f = st.selectbox("Projeto", ["(Todos)"] + df_p["nome_projeto"].tolist(), index=0, key="f_proj")
    with f2:
        status_f = st.selectbox("Status", ["(Todos)"] + STATUS_OPCOES, index=0, key="f_status")
    with f3:
        dt_ini = st.date_input("De (prazo)", value=None, key="f_de")
    with f4:
        dt_fim = st.date_input("Até (prazo)", value=None, key="f_ate")

    df_list = df_a.merge(
        df_p[["id", "nome_projeto"]],
        left_on="projeto_id",
        right_on="id",
        how="left",
        suffixes=("", "_p"),
    )
    df_list = df_list.rename(columns={"nome_projeto": "Projeto"})
    df_list["Prazo"] = df_list["prazo"].apply(_parse_date)

    if proj_f != "(Todos)":
        df_list = df_list[df_list["Projeto"] == proj_f]
    if status_f != "(Todos)":
        df_list = df_list[df_list["status"] == status_f]
    if dt_ini:
        df_list = df_list[df_list["Prazo"].fillna(date(2100, 1, 1)) >= dt_ini]
    if dt_fim:
        df_list = df_list[df_list["Prazo"].fillna(date(1900, 1, 1)) <= dt_fim]

    vis = (
        df_list[["Projeto", "descricao", "responsavel", "status", "Prazo", "criado_em"]]
        .rename(
            columns={
                "descricao": "Descrição",
                "responsavel": "Responsável",
                "status": "Status",
                "criado_em": "Criado em",
            }
        )
        .sort_values(by=["Prazo", "Projeto", "Status"], ascending=[True, True, True])
    )

    st.write("### Atividades")
    st.dataframe(vis, use_container_width=True)

    # ---------- Edição rápida ----------
    st.write("### Editar atividade")
    id_col = "id_x" if "id_x" in df_list.columns else "id"
    id_map = df_list[id_col].tolist()

    if id_map:
        idx = st.selectbox(
            "Selecione uma atividade",
            options=list(range(len(id_map))),
            format_func=lambda i: f"{df_list.iloc[i]['Projeto']} · {df_list.iloc[i]['descricao'][:40]}",
            key="ed_atv_idx",
        )
        if idx is not None:
            atv_id = id_map[idx]
            df_a = load_base("atividades").copy()
            row = df_a[df_a["id"] == atv_id].iloc[0]
            proj_df = load_base("projetos")
            proj_idx_sel = proj_df.index[proj_df["id"] == row["projeto_id"]].tolist()[0]

            proj_e = st.selectbox(
                "Projeto",
                options=list(range(len(proj_df))),
                index=proj_idx_sel,
                format_func=lambda i: proj_df.loc[i, "nome_projeto"],
                key="ed_atv_proj",
            )
            desc_e = st.text_area("Descrição", value=row["descricao"], key="ed_atv_desc")
            prazo_e = st.date_input(
                "Prazo", value=_parse_date(row["prazo"]) or date.today(), key="ed_atv_prazo"
            )
            status_e = st.selectbox(
                "Status",
                STATUS_OPCOES,
                index=max(
                    0,
                    STATUS_OPCOES.index(row["status"]) if row["status"] in STATUS_OPCOES else 0,
                ),
                key="ed_atv_status",
            )
            resp_e = st.text_input("Responsável", value=row.get("responsavel", ""), key="ed_atv_resp")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Salvar alterações", key="ed_atv_salvar"):
                    df_a.loc[df_a["id"] == atv_id, [
                        "projeto_id", "descricao", "prazo", "status", "responsavel", "atualizado_em"
                    ]] = [
                        proj_df.loc[proj_e, "id"],
                        desc_e.strip(),
                        _parse_date(prazo_e).strftime("%Y-%m-%d") if prazo_e else None,
                        status_e,
                        resp_e.strip(),
                        _now_iso(),
                    ]
                    save_base(df_a, "atividades")
                    st.success("Atividade atualizada.")

            with c2:
                if st.button("Excluir atividade", key="ed_atv_excluir"):
                    df_a = df_a[df_a["id"] != atv_id].reset_index(drop=True)
                    save_base(df_a, "atividades")
                    st.warning("Atividade excluída.")

