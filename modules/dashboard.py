import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

from modules.crud_utils import carregar_arquivo_excel

# Bases usadas por outras abas
BASE_ATV = "bases/projetos_atividades.xlsx"
SHEET_ATV = "projetos_atividades"
BASE_PARAM = "bases/projetos_fin_param.xlsx"
SHEET_PARAM = "parametros"
BASE_LANC = "bases/projetos_fin_lanc.xlsx"
SHEET_LANC = "lancamentos"

# Helpers de leitura
@st.cache_data(show_spinner=False)
def _load_df(path, sheet):
    try:
        df = carregar_arquivo_excel(path, sheet_name=sheet)
        if df is None:
            return pd.DataFrame()
        return df.copy()
    except Exception:
        return pd.DataFrame()

# Mini-expansor de fluxo (similar ao do módulo financeiro, simplificado)
def _expandir_fluxo_min(
    dfl: pd.DataFrame,
    projeto: str,
    taxa_anual: float,
    data_base: date,
    inflacao_anual: float = 0.0,
    horizonte_meses: int = 60,
) -> pd.DataFrame:
    if dfl.empty:
        return pd.DataFrame(columns=["competencia", "valor"])
    dfp = dfl[dfl["projeto"] == projeto].copy()
    if dfp.empty:
        return pd.DataFrame(columns=["competencia", "valor"])

    # Despesa negativa, Receita positiva
    dfp["valor"] = np.where(
        dfp["tipo"].str.lower() == "despesa",
        -pd.to_numeric(dfp["valor"], errors="coerce").fillna(0.0),
        pd.to_numeric(dfp["valor"], errors="coerce").fillna(0.0),
    )

    linhas = []
    for _, row in dfp.iterrows():
        start = (
            pd.to_datetime(row.get("data_inicio", data_base), errors="coerce").date()
            if row.get("data_inicio")
            else data_base
        )
        periodicidade = row.get("periodicidade", "Mensal")
        try:
            parcelas = int(pd.to_numeric(row.get("parcelas", 1), errors="coerce").fillna(1))
        except Exception:
            parcelas = int(row.get("parcelas", 1) or 1)
        valor = float(row.get("valor", 0.0)) if not pd.isna(row.get("valor")) else 0.0

        if periodicidade == "Único":
            datas = [start]
        elif periodicidade == "Mensal":
            datas = pd.date_range(start, periods=parcelas, freq="MS").date
        elif periodicidade == "Trimestral":
            datas = pd.date_range(start, periods=parcelas, freq="QS").date
        elif periodicidade == "Anual":
            datas = pd.date_range(start, periods=parcelas, freq="YS").date
        else:
            datas = [start]

        for d in datas:
            if (d - data_base).days / 30.0 > horizonte_meses:
                break
            linhas.append({"competencia": date(d.year, d.month, 1), "valor": valor})

    fluxo = pd.DataFrame(linhas)
    if fluxo.empty:
        return fluxo

    fluxo = (
        fluxo.groupby("competencia", as_index=False)["valor"]
        .sum()
        .sort_values("competencia")
    )

    # Trazer a preços constantes da data-base (opcional)
    if inflacao_anual and inflacao_anual != 0.0:
        i_am = (1 + inflacao_anual) ** (1 / 12) - 1
        meses = (
            (pd.to_datetime(fluxo["competencia"]) - pd.to_datetime(data_base)).dt.days
            // 30
        ).clip(lower=0)
        fluxo["valor"] = fluxo["valor"] / ((1 + i_am) ** meses)

    return fluxo

def _npv_mensal(fluxo: pd.DataFrame, taxa_anual: float, data_base: date) -> float:
    if fluxo.empty:
        return 0.0
    rm = (1 + taxa_anual) ** (1 / 12) - 1  # taxa efetiva mensal
    meses = (
        (pd.to_datetime(fluxo["competencia"]) - pd.to_datetime(data_base)).dt.days // 30
    ).clip(lower=0)
    return float((fluxo["valor"] / ((1 + rm) ** meses)).sum())

def dashboard_principal():
    st.title("📊 Dashboard de Projetos")

    # Carregar bases
    df_atv = _load_df(BASE_ATV, SHEET_ATV)
    df_param = _load_df(BASE_PARAM, SHEET_PARAM)
    df_lanc = _load_df(BASE_LANC, SHEET_LANC)

    # KPIs gerais
    total_itens = len(df_atv) if not df_atv.empty else 0
    concl = int((df_atv["status"] == "Concluído").sum()) if not df_atv.empty else 0
    andamento = int((df_atv["status"] == "Em Andamento").sum()) if not df_atv.empty else 0
    atrasados = int((df_atv["status"] == "Atrasado").sum()) if not df_atv.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Atividades", total_itens)
    c2.metric("Concluídas", concl)
    c3.metric("Em Andamento", andamento)
    c4.metric("Atrasadas", atrasados)

    st.markdown("---")
    st.subheader("💵 ROI por Projeto (VPL)")

    # Projetos candidatos
    projetos = sorted(
        list(
            set(df_atv["projeto"].dropna().unique().tolist() if not df_atv.empty else [])
            | set(df_param["projeto"].dropna().unique().tolist() if not df_param.empty else [])
            | set(df_lanc["projeto"].dropna().unique().tolist() if not df_lanc.empty else [])
        )
    )
    if not projetos:
        st.info("Cadastre projetos em '🗂️ Projetos e Atividades' e parâmetros/lançamentos em '💵 Financeiro do Projeto'.")
        return

    # Montar tabela de VPL por projeto
    rows = []
    for p in projetos:
        # Defaults
        linha = {
            "taxa_desconto_anual": 0.15,
            "data_base": date(date.today().year, date.today().month, 1),
            "indice_inflacao_anual": 0.0,
            "horizonte_meses": 60,
            "moeda": "BRL",
        }
        l = None
        if not df_param.empty and (df_param["projeto"] == p).any():
            l = df_param[df_param["projeto"] == p].iloc[0].to_dict()
            linha.update(l)
        fluxo = _expandir_fluxo_min(
            df_lanc,
            p,
            float(linha["taxa_desconto_anual"]),
            linha["data_base"],
            float(linha["indice_inflacao_anual"]),
            int(linha["horizonte_meses"]),
        )
        vpl = (
            _npv_mensal(fluxo, float(linha["taxa_desconto_anual"]), linha["data_base"])
            if not fluxo.empty
            else 0.0
        )
        rows.append(
            {
                "projeto": p,
                "vpl": vpl,
                "wacc": linha["taxa_desconto_anual"],
                "moeda": (l.get("moeda", "BRL") if isinstance(l, dict) else "BRL"),
            }
        )

    df_vpl = pd.DataFrame(rows).sort_values("vpl", ascending=False)
    st.dataframe(df_vpl, use_container_width=True, hide_index=True)

    # Gráfico de barras do VPL por projeto
    if not df_vpl.empty:
        st.bar_chart(df_vpl.set_index("projeto")["vpl"])

    st.markdown("---")
    st.subheader("📅 Próximas Entregas (30 dias)")
    if df_atv.empty:
        st.caption("Sem atividades cadastradas.")
    else:
        df_atv_show = df_atv.copy()
        df_atv_show["fim"] = pd.to_datetime(df_atv_show["fim"], errors="coerce")
        proximas = (
            df_atv_show.dropna(subset=["fim"])
            .query(
                "fim >= @pd.Timestamp('today').normalize() and "
                "fim <= @pd.Timestamp('today').normalize() + @pd.Timedelta(days=30)"
            )
            .sort_values("fim")[
                ["projeto", "atividade", "responsavel", "status", "prioridade", "fim"]
            ]
        )
        if proximas.empty:
            st.caption("Sem entregas no próximo mês.")
        else:
            proximas["fim"] = proximas["fim"].dt.strftime("%Y-%m-%d")
            st.dataframe(
                proximas.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")
    st.subheader("🔗 Atalhos")
    colA, colB, colC = st.columns(3)
    with colA:
        if st.button("Abrir Projetos e Atividades"):
            st.session_state["menu"] = "🗂️ Projetos e Atividades"
            st.experimental_rerun()
    with colB:
        if st.button("Abrir Financeiro do Projeto"):
            st.session_state["menu"] = "💵 Financeiro do Projeto"
            st.experimental_rerun()
    with colC:
        if st.button("Abrir Pontos Focais"):
            st.session_state["menu"] = "👥 Pontos Focais"
            st.experimental_rerun()
