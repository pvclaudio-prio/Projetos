# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from common import load_base, _parse_date, _sev_to_score, _prob_to_score

def _fill_series(dst: pd.Series, src: pd.Series | str | None, default=""):
    """Preenche valores vazios/NaN de `dst` com `src` (ou default)."""
    if isinstance(src, pd.Series):
        fallback = src
    elif isinstance(src, str) and src in ("", "None"):
        fallback = default
    else:
        fallback = src
    # vazio = NaN ou string em branco
    mask_empty = dst.isna() | dst.astype(str).str.strip().eq("")
    if isinstance(fallback, pd.Series):
        return dst.where(~mask_empty, fallback)
    else:
        return dst.where(~mask_empty, default if fallback is None else fallback)

def _coerce_riscos(df_r: pd.DataFrame) -> pd.DataFrame:
    """Normaliza diferentes esquemas de riscos para um conjunto comum."""
    if df_r.empty:
        return df_r

    r = df_r.copy()

    # categoria: preferir 'categoria'; se vazia, usar 'titulo'
    if "categoria" not in r.columns:
        r["categoria"] = r.get("titulo", "")
    else:
        r["categoria"] = _fill_series(r["categoria"], r.get("titulo", ""), "")

    # descricao: usar 'descricao' se houver; senão ficar vazio
    if "descricao" not in r.columns:
        r["descricao"] = r.get("Descrição", r.get("desc", ""))
    else:
        r["descricao"] = _fill_series(r["descricao"], r.get("Descrição", r.get("desc", "")), "")

    # severidade: se não houver, mapear de 'impacto'
    if "severidade" not in r.columns:
        if "impacto" in r.columns:
            mapa = {"Baixo": "Baixo", "Médio": "Médio", "Medio": "Médio", "Alto": "Alto", "Crítico": "Crítico", "Critico": "Crítico"}
            r["severidade"] = r["impacto"].map(lambda x: mapa.get(str(x), "Médio"))
        else:
            r["severidade"] = "Médio"
    else:
        if "impacto" in r.columns:
            mapa = {"Baixo": "Baixo", "Médio": "Médio", "Medio": "Médio", "Alto": "Alto", "Crítico": "Crítico", "Critico": "Crítico"}
            r["severidade"] = _fill_series(r["severidade"], r["impacto"].map(lambda x: mapa.get(str(x), "Médio")), "Médio")
        else:
            r["severidade"] = _fill_series(r["severidade"], None, "Médio")

    # probabilidade: manter se existir; senão tentar 'prob' ou default
    if "probabilidade" not in r.columns:
        r["probabilidade"] = r.get("prob", r.get("Probabilidade", "Possível"))
    else:
        r["probabilidade"] = _fill_series(r["probabilidade"], r.get("prob", r.get("Probabilidade", "Possível")), "Possível")

    # status_tratativa: se não existir ou estiver vazio, usar 'status'
    if "status_tratativa" not in r.columns:
        r["status_tratativa"] = r.get("status", "Aberto")
    else:
        r["status_tratativa"] = _fill_series(r["status_tratativa"], r.get("status", "Aberto"), "Aberto")

    # responsavel
    if "responsavel" not in r.columns:
        r["responsavel"] = r.get("responsável", "")
    else:
        r["responsavel"] = _fill_series(r["responsavel"], r.get("responsável", ""), "")

    # prazo_tratativa: se não existir, tentar 'prazo'; normalizar data
    if "prazo_tratativa" not in r.columns:
        r["prazo_tratativa"] = r.get("prazo", None)
    r["prazo_tratativa"] = r["prazo_tratativa"].apply(_parse_date)

    # impacto_financeiro: default 0.0
    if "impacto_financeiro" not in r.columns:
        r["impacto_financeiro"] = 0.0
    r["impacto_financeiro"] = r["impacto_financeiro"].fillna(0.0)

    # Score p/ priorização
    r["Score"] = r.apply(
        lambda x: _sev_to_score(str(x.get("severidade", ""))) * _prob_to_score(str(x.get("probabilidade", ""))),
        axis=1,
    )
    return r

def aba_visao_unificada(st):
    st.subheader("📊 Visão Unificada do Projeto")
    st.caption("Resumo 360°: escopo, atividades, riscos, financeiro e pontos focais, numa única tela.")

    df_p  = load_base("projetos").copy()
    df_a  = load_base("atividades").copy()
    df_f  = load_base("financeiro").copy()
    df_pf = load_base("pontos_focais").copy()
    df_r  = load_base("riscos").copy()

    if df_p.empty:
        st.info("Cadastre ao menos um projeto para visualizar.")
        return

    proj = st.selectbox("Projeto", df_p["nome_projeto"].tolist())
    pid = df_p.loc[df_p["nome_projeto"] == proj, "id"].iloc[0]

    colA, colB, colC = st.columns([2,1,1])

    # Escopo
    with colA:
        st.write("### Escopo")
        st.write(df_p.loc[df_p["id"] == pid, "escopo"].iloc[0] or "(Sem escopo registrado)")

    # KPIs de atividades
    df_a_p = df_a[df_a.get("projeto_id", "") == pid].copy()
    hoje = date.today()
    if not df_a_p.empty:
        df_a_p["Prazo"] = df_a_p["prazo"].apply(_parse_date)
        abertas = df_a_p[df_a_p["status"] != "Concluída"]
        atv_total = len(df_a_p)
        atv_vencidas = len(abertas[(abertas["Prazo"].notna()) & (abertas["Prazo"] < hoje)])
        atv_hoje = len(abertas[abertas["Prazo"] == hoje])
    else:
        atv_total = atv_vencidas = atv_hoje = 0

    # Riscos (normalizados)
    df_r_p = _coerce_riscos(df_r[df_r.get("projeto_id", "") == pid].copy())
    if not df_r_p.empty:
        riscos_abertos = len(df_r_p[df_r_p["status_tratativa"].astype(str).isin(["Aberto","Em tratamento","Mitigando","Aberto "])])
        risco_top = df_r_p.sort_values("Score", ascending=False).head(1)
        risco_top_txt = (
            f"{risco_top.iloc[0]['categoria']}: {str(risco_top.iloc[0]['descricao'])[:80]} (Score {int(risco_top.iloc[0]['Score'])})"
            if not risco_top.empty else "—"
        )
    else:
        riscos_abertos = 0
        risco_top_txt = "—"

    # Financeiro (saldo)
    df_f_p = df_f[df_f.get("projeto_id", "") == pid].copy()
    if not df_f_p.empty:
        saldo = (df_f_p["valor"] * df_f_p["tipo"].map({"Entrada": 1, "Saída": -1})).sum()
    else:
        saldo = 0.0

    with colB:
        st.metric("Atividades (total)", atv_total)
        st.metric("Vencidas", atv_vencidas)
        st.metric("Vencem hoje", atv_hoje)
    with colC:
        st.metric("Riscos abertos", riscos_abertos)
        st.metric("Saldo (BRL)", f"{saldo:,.2f}")
        st.caption(f"Top risco: {risco_top_txt}")

    st.divider()

    # Detalhes
    c1, c2 = st.columns(2)

    with c1:
        st.write("#### Atividades")
        if df_a_p.empty:
            st.caption("Sem atividades.")
        else:
            df_view = df_a_p.sort_values(["status", "prazo", "descricao"])[
                ["descricao", "responsavel", "status", "prazo"]
            ].rename(columns={"descricao": "Descrição", "responsavel": "Responsável", "prazo": "Prazo"})
            st.dataframe(df_view, use_container_width=True)

    with c2:
        st.write("#### Riscos")
        if df_r_p.empty:
            st.caption("Sem riscos.")
        else:
            st.dataframe(
                df_r_p[[
                    "categoria","descricao","severidade","probabilidade",
                    "status_tratativa","responsavel","prazo_tratativa","impacto_financeiro","Score"
                ]].rename(columns={
                    "categoria": "Categoria","descricao": "Descrição","severidade": "Severidade",
                    "probabilidade": "Probabilidade","status_tratativa": "Status",
                    "responsavel": "Responsável","prazo_tratativa": "Prazo tratativa",
                    "impacto_financeiro": "Impacto (BRL)"
                }).sort_values(["Score"], ascending=False),
                use_container_width=True,
            )

    st.write("#### Financeiro")
    if df_f_p.empty:
        st.caption("Sem lançamentos financeiros.")
    else:
        st.dataframe(
            df_f_p[["data","categoria","descricao","valor","tipo"]]
            .rename(columns={"data":"Data","categoria":"Categoria","descricao":"Descrição","valor":"Valor","tipo":"Tipo"})
            .sort_values(["Data"]),
            use_container_width=True,
        )

    st.write("#### Pontos Focais")
    df_pf = load_base("pontos_focais").copy()
    df_pf_p = df_pf[df_pf.get("projeto_id","") == pid].copy()
    if df_pf_p.empty:
        st.caption("Sem pontos focais.")
    else:
        st.dataframe(
            df_pf_p[["nome","email","telefone","funcao","observacoes"]]
            .rename(columns={"nome":"Nome","email":"E-mail","telefone":"Telefone","funcao":"Função","observacoes":"Observações"})
            .sort_values(["Nome"]),
            use_container_width=True,
        )
