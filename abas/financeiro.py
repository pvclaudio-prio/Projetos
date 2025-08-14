# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import List, Tuple
import numpy as np
import pandas as pd
import streamlit as st

from common import load_base, save_base, _now_iso, _parse_date

# ---------------------------
# Utilidades financeiras
# ---------------------------
def _to_month(dt: date) -> date:
    """Normaliza uma data para o primeiro dia do mês."""
    return date(dt.year, dt.month, 1)

def _aggregate_monthly(cashflows: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DF com colunas: data (str ou date), valor (float), tipo ('Entrada'/'Saída')
    Retorna DF agregado por mês com colunas: mes(date), fluxo(float)
    """
    if cashflows.empty:
        return pd.DataFrame(columns=["mes", "fluxo"])

    df = cashflows.copy()
    df["data"] = df["data"].apply(_parse_date)
    df = df[df["data"].notna()]
    if df.empty:
        return pd.DataFrame(columns=["mes", "fluxo"])

    # Sinal: entrada +, saída -
    df["valor_signed"] = df.apply(
        lambda r: r["valor"] if str(r.get("tipo", "")).strip().lower() == "entrada" else -r["valor"],
        axis=1,
    )
    df["mes"] = df["data"].apply(_to_month)
    monthly = (
        df.groupby("mes")["valor_signed"]
        .sum()
        .reset_index()
        .rename(columns={"valor_signed": "fluxo"})
        .sort_values("mes")
        .reset_index(drop=True)
    )
    return monthly

def _npv(rate_monthly: float, flows: List[Tuple[int, float]]) -> float:
    """
    VPL mensal: flows é lista de (n, valor) com n=0 no 1º mês da série.
    rate_monthly = taxa de desconto ao mês (ex.: 1% -> 0.01)
    """
    if not flows:
        return 0.0
    return float(sum(v / ((1 + rate_monthly) ** n) for n, v in flows))

def _irr(flows: List[float], guess: float = 0.1) -> float | None:
    """
    TIR (mensal) por Newton-Raphson (máx. 100 iterações).
    Retorna None se não convergir ou série trivial.
    """
    if len(flows) < 2 or all(abs(x) < 1e-12 for x in flows):
        return None

    r = guess
    for _ in range(100):
        try:
            denom = [(1 + r) ** i for i in range(len(flows))]
        except Exception:
            return None
        npv = sum(cf / d for cf, d in zip(flows, denom))
        d_npv = sum(-i * cf / ((1 + r) ** (i + 1)) for i, cf in enumerate(flows))
        if abs(d_npv) < 1e-12:
            return None
        r_new = r - npv / d_npv
        if abs(r_new - r) < 1e-9:
            if -0.9999 < r_new < 10:
                return float(r_new)
            return None
        r = r_new
    return None

def _payback_months(flows: List[float]) -> float | None:
    """
    Payback em meses (pode retornar fração).
    Considera série já agregada mensalmente a partir de n=0.
    """
    cum = 0.0
    for i, cf in enumerate(flows):
        prev = cum
        cum += cf
        if prev < 0 <= cum:
            need = -prev
            frac = 0.0 if abs(cf) < 1e-12 else need / cf
            return i + frac
    return None

def _format_pct(v: float | None, scale: float = 1.0) -> str:
    if v is None:
        return "—"
    return f"{(v*scale):.2%}"

def _format_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ---------------------------
# Aba principal
# ---------------------------
def aba_financeiro(st):
    st.subheader("💰 Financeiro do Projeto")
    st.caption("Registre lançamentos por projeto e avalie a viabilidade (VPL, TIR, Payback).")

    df_p = load_base("projetos").copy()
    df_f = load_base("financeiro").copy()

    if df_p.empty:
        st.info("Cadastre um projeto na aba 'Projetos & Escopo' antes de lançar financeiro.")
        return

    # ----------------- Novo lançamento -----------------
    with st.expander("➕ Novo lançamento", expanded=False):
        proj_idx = st.selectbox(
            "Projeto",
            options=list(range(len(df_p))),
            format_func=lambda i: df_p.loc[i, "nome_projeto"],
            key="nf_proj",
        )
        data_l = st.date_input("Data", key="nf_data")
        categoria = st.text_input("Categoria", key="nf_cat")
        descricao = st.text_input("Descrição", key="nf_desc")
        valor = st.number_input("Valor (BRL)", min_value=0.0, step=0.01, key="nf_valor")
        tipo = st.selectbox("Tipo", ["Entrada", "Saída"], key="nf_tipo")
        if st.button("Salvar lançamento", type="primary", key="nf_salvar"):
            novo = {
                "id": str(uuid.uuid4()),
                "projeto_id": df_p.loc[proj_idx, "id"],
                "data": _parse_date(data_l).strftime("%Y-%m-%d") if data_l else None,
                "categoria": categoria.strip(),
                "descricao": descricao.strip(),
                "valor": float(valor),
                "tipo": tipo,
                "criado_em": _now_iso(),
                "atualizado_em": _now_iso(),
            }
            df_f = pd.concat([df_f, pd.DataFrame([novo])], ignore_index=True)
            save_base(df_f, "financeiro")
            st.success("Lançamento salvo.")

    if df_f.empty:
        st.info("Nenhum lançamento registrado.")
        return

    # ----------------- Lista + filtros -----------------
    df_fx = df_f.merge(
        df_p[["id", "nome_projeto"]],
        left_on="projeto_id",
        right_on="id",
        how="left",
    ).rename(columns={"nome_projeto": "Projeto"})

    c1, c2 = st.columns(2)
    with c1:
        proj_f = st.selectbox("Projeto", ["(Todos)"] + df_p["nome_projeto"].tolist(), index=0, key="ff_proj")
    with c2:
        tipo_f = st.selectbox("Tipo", ["(Todos)", "Entrada", "Saída"], index=0, key="ff_tipo")

    df_list = df_fx.copy()
    if proj_f != "(Todos)":
        df_list = df_list[df_list["Projeto"] == proj_f]
    if tipo_f != "(Todos)":
        df_list = df_list[df_list["tipo"] == tipo_f]

    st.write("### Lançamentos")
    st.dataframe(
        df_list[["Projeto", "data", "categoria", "descricao", "valor", "tipo"]]
        .rename(
            columns={
                "data": "Data",
                "categoria": "Categoria",
                "descricao": "Descrição",
                "valor": "Valor",
                "tipo": "Tipo",
            }
        )
        .sort_values(["Projeto", "Data"]),
        use_container_width=True,
    )

    # ----------------- Resumo por projeto -----------------
    if not df_list.empty:
        resumo = df_list.copy()
        resumo["sign"] = np.where(resumo["tipo"].fillna("").eq("Entrada"), 1, -1)
        resumo = (
            resumo.groupby("Projeto")
            .apply(lambda d: (d["valor"] * d["sign"]).sum())
            .reset_index(name="Saldo")
        )
        st.write("### Saldo por projeto")
        st.dataframe(resumo, use_container_width=True)

    # ----------------- Indicadores de Viabilidade -----------------
    st.divider()
    st.write("## Indicadores de Viabilidade")

    proj_escolhido = st.selectbox(
        "Escolha o projeto para calcular VPL/TIR/Payback",
        df_p["nome_projeto"].tolist(),
        key="sel_proj_indicadores",
    )
    pid = df_p.loc[df_p["nome_projeto"] == proj_escolhido, "id"].iloc[0]

    with st.expander("⚙️ Parâmetros de cálculo", expanded=True):
        taxa_aa = st.number_input(
            "Taxa de desconto ao ano (%)",
            min_value=0.0,
            max_value=100.0,
            value=12.0,
            step=0.25,
            key="tx_aa",
        )
        taxa_am = (1 + taxa_aa / 100.0) ** (1 / 12) - 1
        st.caption(f"Taxa equivalente ao mês: **{taxa_am:.2%}**")

        considerar_apartir = st.date_input("Considerar lançamentos a partir de", value=None, key="apartir")

    df_proj = df_f[df_f["projeto_id"] == pid].copy()
    if considerar_apartir:
        d0 = _parse_date(considerar_apartir)
        df_proj["data"] = df_proj["data"].apply(_parse_date)
        df_proj = df_proj[df_proj["data"] >= d0]

    if df_proj.empty:
        st.info("Sem lançamentos para o projeto selecionado.")
        return

    tot_entradas = df_proj[df_proj["tipo"] == "Entrada"]["valor"].sum()
    tot_saidas = df_proj[df_proj["tipo"] == "Saída"]["valor"].sum()
    saldo = tot_entradas - tot_saidas

    k1, k2, k3 = st.columns(3)
    k1.metric("Entradas (Σ)", _format_money(tot_entradas))
    k2.metric("Saídas (Σ)", _format_money(tot_saidas))
    k3.metric("Saldo (Entradas - Saídas)", _format_money(saldo))

    # Série mensal (Entradas +, Saídas -)
    serie = _aggregate_monthly(df_proj[["data", "valor", "tipo"]])
    if serie.empty:
        st.warning("Não há datas válidas para calcular indicadores.")
        return

    serie = serie.sort_values("mes").reset_index(drop=True)
    n0 = serie["mes"].iloc[0]
    serie["n"] = serie["mes"].apply(lambda d: (d.year - n0.year) * 12 + (d.month - n0.month))

    flows_pairs = list(zip(serie["n"].tolist(), serie["fluxo"].tolist()))
    flows_only = [v for _, v in flows_pairs]

    vpl = _npv(taxa_am, flows_pairs)
    tir_m = _irr(flows_only, guess=0.05)
    tir_a = None if tir_m is None else (1 + tir_m) ** 12 - 1
    payback_meses = _payback_months(flows_only)

    cA, cB, cC, cD = st.columns(4)
    cA.metric("VPL (mensal)", _format_money(vpl))
    cB.metric("TIR (a.m.)", _format_pct(tir_m))
    cC.metric("TIR (a.a.)", _format_pct(tir_a))
    cD.metric("Payback (meses)", "—" if payback_meses is None else f"{payback_meses:.1f}")

    viavel = (vpl > 0) and (tir_a is not None) and (tir_a > (taxa_aa / 100.0))
    st.markdown(
        f"**Viabilidade:** {'✅ Viável' if viavel else '⚠️ Não Viável (pelos parâmetros atuais)'}  \n"
        f"_Critério:_ VPL > 0 e TIR (a.a.) > taxa de desconto (a.a.)."
    )

    with st.expander("📈 Série mensal utilizada nos cálculos"):
        vis = serie[["mes", "fluxo"]].rename(columns={"mes": "Mês", "fluxo": "Fluxo (R$)"})
        st.dataframe(vis, use_container_width=True)
