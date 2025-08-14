# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
import pandas as pd
from datetime import date
import streamlit as st
from common import (
    load_base, save_base, _parse_date, _now_iso,
    RISCO_SEVERIDADE, RISCO_PROBABILIDADE, RISCO_STATUS
)

def _fmt_date(d):
    d = _parse_date(d)
    return d.strftime("%Y-%m-%d") if d else None

def aba_riscos(st):
    st.subheader("⚠️ Riscos do Projeto")
    st.caption("Cadastre, edite e exclua riscos. Campos compatíveis com Agenda e Visão Unificada.")

    df_proj = load_base("projetos").copy()
    if df_proj.empty:
        st.info("Cadastre um projeto na aba **Projetos & Escopo** antes de registrar riscos.")
        return

    df_ris = load_base("riscos").copy()

    # ------------------------- Cadastro -------------------------
    st.write("### Adicionar novo risco")
    with st.form("form_novo_risco", clear_on_submit=True):
        proj_idx = st.selectbox(
            "Projeto", options=list(range(len(df_proj))),
            format_func=lambda i: df_proj.loc[i, "nome_projeto"],
            key="rk_proj_novo",
        )
        categoria = st.text_input("Categoria do risco", key="rk_cat_novo")
        descricao = st.text_area("Descrição do risco", key="rk_desc_novo")
        severidade = st.selectbox("Severidade", RISCO_SEVERIDADE, index=1, key="rk_sev_novo")
        probabilidade = st.selectbox("Probabilidade", RISCO_PROBABILIDADE, index=2, key="rk_prob_novo")
        status_tratativa = st.selectbox("Status da tratativa", RISCO_STATUS, index=0, key="rk_stat_novo")
        responsavel = st.text_input("Responsável", key="rk_resp_novo")
        prazo_tratativa = st.date_input("Prazo da tratativa", value=None, key="rk_prazo_novo")
        impacto_financeiro = st.number_input("Impacto financeiro estimado (BRL)", min_value=0.0, step=100.0, key="rk_imp_novo")

        submitted = st.form_submit_button("Salvar risco", type="primary")
        if submitted:
            novo = {
                "id": str(uuid.uuid4()),
                "projeto_id": df_proj.loc[proj_idx, "id"],
                "categoria": categoria.strip(),
                "descricao": descricao.strip(),
                "severidade": severidade,
                "probabilidade": probabilidade,
                "status_tratativa": status_tratativa,
                "responsavel": responsavel.strip(),
                "prazo_tratativa": _fmt_date(prazo_tratativa),
                "impacto_financeiro": float(impacto_financeiro),
                "criado_em": _now_iso(),
                "atualizado_em": _now_iso(),
            }
            df_ris = pd.concat([df_ris, pd.DataFrame([novo])], ignore_index=True)
            save_base(df_ris, "riscos")
            st.success("Risco salvo com sucesso.")

    # ------------------------- Lista -------------------------
    if df_ris.empty:
        st.info("Nenhum risco cadastrado ainda.")
        return

    df_list = df_ris.merge(
        df_proj[["id", "nome_projeto"]],
        left_on="projeto_id", right_on="id", how="left"
    ).rename(columns={"nome_projeto": "Projeto"})

    # selecione colunas para exibição
    cols = [
        "Projeto","categoria","descricao","severidade","probabilidade",
        "status_tratativa","responsavel","prazo_tratativa","impacto_financeiro"
    ]
    exist_cols = [c for c in cols if c in df_list.columns]
    df_view = df_list[exist_cols].copy()

    # ordenar ANTES de renomear (evita KeyError)
    sort_keys = [c for c in ["Projeto","severidade","probabilidade"] if c in df_view.columns]
    if sort_keys:
        # severidade/probabilidade desc (alto primeiro) e projeto asc
        ascending = [True] + [False]*(len(sort_keys)-1) if sort_keys[0] == "Projeto" else [False]*len(sort_keys)
        df_view = df_view.sort_values(sort_keys, ascending=ascending)

    st.write("### Riscos mapeados")
    st.dataframe(
        df_view.rename(columns={
            "categoria":"Categoria","descricao":"Descrição","severidade":"Severidade",
            "probabilidade":"Probabilidade","status_tratativa":"Status",
            "responsavel":"Responsável","prazo_tratativa":"Prazo tratativa",
            "impacto_financeiro":"Impacto (BRL)"
        }),
        use_container_width=True
    )

    # ------------------------- Edição / Exclusão -------------------------
    st.write("### Editar / Excluir risco")
    proj_sel = st.selectbox("Projeto", ["(Todos)"] + df_proj["nome_projeto"].tolist(), key="rk_proj_filtro")
    base_ed = df_list if proj_sel == "(Todos)" else df_list[df_list["Projeto"] == proj_sel]

    if base_ed.empty:
        st.caption("Nenhum risco para editar nesse filtro.")
        return

    id_col = "id_x" if "id_x" in base_ed.columns else "id"
    idx = st.selectbox(
        "Escolha o risco",
        options=list(range(len(base_ed))),
        format_func=lambda i: f"{base_ed.iloc[i]['Projeto']} · {base_ed.iloc[i]['categoria']} · {str(base_ed.iloc[i]['descricao'])[:50]}",
        key="rk_idx_ed"
    )
    if idx is None:
        return

    rk_id = base_ed.iloc[idx][id_col]
    df_ris = load_base("riscos").copy()
    row = df_ris[df_ris["id"] == rk_id].iloc[0]

    with st.form("form_edit_risco"):
        proj_idx_e = df_proj.index[df_proj["id"] == row["projeto_id"]].tolist()
        proj_idx_e = proj_idx_e[0] if proj_idx_e else 0
        proj_e = st.selectbox(
            "Projeto", options=list(range(len(df_proj))), index=proj_idx_e,
            format_func=lambda i: df_proj.loc[i, "nome_projeto"], key="rk_proj_edit"
        )

        cat_e = st.text_input("Categoria", value=row.get("categoria",""), key="rk_cat_edit")
        desc_e = st.text_area("Descrição", value=row.get("descricao",""), key="rk_desc_edit")
        sev_e  = st.selectbox("Severidade", RISCO_SEVERIDADE,
                              index=max(0, RISCO_SEVERIDADE.index(row.get("severidade", RISCO_SEVERIDADE[1]))),
                              key="rk_sev_edit")
        prob_e = st.selectbox("Probabilidade", RISCO_PROBABILIDADE,
                              index=max(0, RISCO_PROBABILIDADE.index(row.get("probabilidade", RISCO_PROBABILIDADE[2]))),
                              key="rk_prob_edit")
        stat_e = st.selectbox("Status da tratativa", RISCO_STATUS,
                              index=max(0, RISCO_STATUS.index(row.get("status_tratativa", RISCO_STATUS[0]))),
                              key="rk_stat_edit")
        resp_e = st.text_input("Responsável", value=row.get("responsavel",""), key="rk_resp_edit")
        prazo_e = st.date_input("Prazo da tratativa", value=_parse_date(row.get("prazo_tratativa")), key="rk_prazo_edit")
        imp_e = st.number_input("Impacto financeiro (BRL)", min_value=0.0, step=100.0,
                                value=float(row.get("impacto_financeiro", 0.0)), key="rk_imp_edit")

        c1, c2 = st.columns(2)
        salvar = c1.form_submit_button("Salvar alterações", type="primary")
        excluir = c2.form_submit_button("Excluir risco", type="secondary")

    if salvar:
        df_ris.loc[df_ris["id"] == rk_id, [
            "projeto_id","categoria","descricao","severidade","probabilidade",
            "status_tratativa","responsavel","prazo_tratativa","impacto_financeiro","atualizado_em"
        ]] = [
            df_proj.loc[proj_e, "id"], cat_e.strip(), desc_e.strip(), sev_e, prob_e,
            stat_e, resp_e.strip(), _fmt_date(prazo_e), float(imp_e), _now_iso()
        ]
        save_base(df_ris, "riscos")
        st.success("Risco atualizado.")

    if excluir:
        df_ris = df_ris[df_ris["id"] != rk_id].reset_index(drop=True)
        save_base(df_ris, "riscos")
        st.warning("Risco excluído.")
