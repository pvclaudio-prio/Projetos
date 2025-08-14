import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
import uuid

from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel
from modules.core_context import (
    seletor_contexto,
    validar_projeto_atividade_valido,
    load_df_atividades,
    list_projetos,
)

# ──────────────────────────────────────────────────────────────────────────────
# Caminhos das bases
BASE_PARAM = "bases/projetos_fin_param.xlsx"
SHEET_PARAM = "parametros"
BASE_LANC = "bases/projetos_fin_lanc.xlsx"
SHEET_LANC = "lancamentos"

# Schema
COLS_PARAM = [
    "projeto",                # chave textual igual à usada em Projetos e Atividades
    "taxa_desconto_anual",   # ex.: 0.15 = 15% a.a.
    "horizonte_meses",       # horizonte de análise para expandir fluxo
    "data_base",             # data base (início do fluxo)
    "indice_inflacao_anual", # opcional: inflação p/ trazer valores a preços constantes
    "moeda",                 # BRL, USD, etc
    "cenario",               # Base, Alto, Baixo
    "observacoes",
    "atualizado_em",
]

COLS_LANC = [
    "id", "projeto", "tipo", "categoria", "descricao",
    "valor", "data_inicio", "periodicidade", "parcelas",
    "eh_estimativa", "confianca", "cenario", "capex_opex",
    "fornecedor", "centro_custo", "observacoes", "criado_em", "atualizado_em"
]

TIPOS = ["Receita", "Despesa"]
PERIODICIDADES = ["Único", "Mensal", "Trimestral", "Anual"]
CENARIOS = ["Base", "Alto", "Baixo"]
CAPEX_OPEX = ["CAPEX", "OPEX"]

# ──────────────────────────────────────────────────────────────────────────────
# Loads & Saves

@st.cache_data(show_spinner=False)
def _load_params() -> pd.DataFrame:
    try:
        df = carregar_arquivo_excel(BASE_PARAM, sheet_name=SHEET_PARAM)
        if df is None or df.empty:
            df = pd.DataFrame(columns=COLS_PARAM)
    except Exception:
        df = pd.DataFrame(columns=COLS_PARAM)

    for c in COLS_PARAM:
        if c not in df.columns:
            df[c] = None

    if not df.empty:
        df["taxa_desconto_anual"] = pd.to_numeric(df["taxa_desconto_anual"], errors="coerce").fillna(0.0)
        df["horizonte_meses"] = pd.to_numeric(df["horizonte_meses"], errors="coerce").fillna(60).astype(int)
        df["indice_inflacao_anual"] = pd.to_numeric(df["indice_inflacao_anual"], errors="coerce").fillna(0.0)
        df["data_base"] = pd.to_datetime(df["data_base"], errors="coerce").dt.date
        for c in ["projeto", "moeda", "cenario", "observacoes"]:
            df[c] = df[c].fillna("").astype(str)
    return df[COLS_PARAM].copy()

@st.cache_data(show_spinner=False)
def _load_lanc() -> pd.DataFrame:
    try:
        df = carregar_arquivo_excel(BASE_LANC, sheet_name=SHEET_LANC)
        if df is None or df.empty:
            df = pd.DataFrame(columns=COLS_LANC)
    except Exception:
        df = pd.DataFrame(columns=COLS_LANC)

    for c in COLS_LANC:
        if c not in df.columns:
            df[c] = None

    if not df.empty:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        df["parcelas"] = pd.to_numeric(df["parcelas"], errors="coerce").fillna(1).astype(int)
        df["data_inicio"] = pd.to_datetime(df["data_inicio"], errors="coerce").dt.date
        for c in ["projeto","tipo","categoria","descricao","periodicidade","cenario","capex_opex","fornecedor","centro_custo","observacoes"]:
            df[c] = df[c].fillna("").astype(str)
        df["eh_estimativa"] = df["eh_estimativa"].fillna(True).astype(bool)
        df["confianca"] = pd.to_numeric(df["confianca"], errors="coerce").fillna(0.7)
    return df[COLS_LANC].copy()

def _save_params(df: pd.DataFrame):
    df = df[COLS_PARAM].copy()
    df["data_base"] = df["data_base"].apply(lambda x: x.isoformat() if isinstance(x, date) else (x or ""))
    df["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_arquivo_excel(df, BASE_PARAM, sheet_name=SHEET_PARAM)
    _load_params.clear()

def _save_lanc(df: pd.DataFrame):
    df = df[COLS_LANC].copy()
    df["data_inicio"] = df["data_inicio"].apply(lambda x: x.isoformat() if isinstance(x, date) else (x or ""))
    df["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_arquivo_excel(df, BASE_LANC, sheet_name=SHEET_LANC)
    _load_lanc.clear()

# ──────────────────────────────────────────────────────────────────────────────
# Cálculos financeiros

def _expandir_fluxo(df_lanc: pd.DataFrame, projeto: str, params: dict) -> pd.DataFrame:
    """Gera fluxo de caixa mensal expandido a partir dos lançamentos do projeto.
    Retorna DF com colunas: competencia, projeto, valor (positivo=receita, negativo=despesa)"""
    if not projeto:
        return pd.DataFrame(columns=["competencia","projeto","valor","tipo","categoria","descricao"])

    inflacao_aa = float(params.get("indice_inflacao_anual", 0.0))
    horizonte = int(params.get("horizonte_meses", 60))
    data_base = params.get("data_base") or date.today()
    if isinstance(data_base, str):
        data_base = pd.to_datetime(data_base).date()

    dfp = df_lanc[(df_lanc["projeto"] == projeto)].copy()
    if "cenario" in dfp.columns and params.get("cenario"):
        dfp = dfp[dfp["cenario"].eq(params["cenario"]) | dfp["cenario"].eq("")]

    # Receita positiva, Despesa negativa
    dfp["valor"] = np.where(dfp["tipo"].str.lower()=="despesa", -dfp["valor"], dfp["valor"])

    linhas = []
    for _, row in dfp.iterrows():
        start = row["data_inicio"] or data_base
        if isinstance(start, str):
            start = pd.to_datetime(start).date()
        periodicidade = row.get("periodicidade", "Mensal")
        parcelas = int(row.get("parcelas", 1))
        valor = float(row.get("valor", 0.0))

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
            if (d - data_base).days/30.0 > horizonte:
                break
            linhas.append({
                "competencia": date(d.year, d.month, 1),
                "projeto": projeto,
                "valor": valor,
                "tipo": row.get("tipo",""),
                "categoria": row.get("categoria",""),
                "descricao": row.get("descricao",""),
            })
    fluxo = pd.DataFrame(linhas)
    if fluxo.empty:
        return pd.DataFrame(columns=["competencia","projeto","valor","tipo","categoria","descricao"])

    # Agregar por mês
    fluxo = fluxo.groupby(["competencia","projeto"], as_index=False)["valor"].sum()

    # Ajuste por inflação (opcional): trazer a preços constantes da data_base
    if inflacao_aa and inflacao_aa != 0.0:
        i_am = (1 + inflacao_aa) ** (1/12) - 1
        fluxo = fluxo.sort_values("competencia")
        meses = ((pd.to_datetime(fluxo["competencia"]) - pd.to_datetime(data_base)).dt.days // 30).clip(lower=0)
        fluxo["valor"] = fluxo["valor"] / ((1 + i_am) ** meses)

    return fluxo

def _npv(fluxo: pd.DataFrame, taxa_anual: float, data_base: date) -> float:
    if fluxo.empty:
        return 0.0
    rm = (1 + taxa_anual) ** (1/12) - 1
    meses = ((pd.to_datetime(fluxo["competencia"]) - pd.to_datetime(data_base)).dt.days // 30).clip(lower=0)
    return float((fluxo["valor"] / ((1 + rm) ** meses)).sum())

def _payback(fluxo: pd.DataFrame, descontado: bool, taxa_anual: float, data_base: date) -> int | None:
    if fluxo.empty:
        return None
    rm = (1 + taxa_anual) ** (1/12) - 1
    fluxo = fluxo.sort_values("competencia").copy()
    saldo = 0.0
    for _, row in fluxo.iterrows():
        t = max(0, (pd.to_datetime(row["competencia"]) - pd.to_datetime(data_base)).days // 30)
        v = row["valor"] / ((1 + rm) ** t) if descontado else row["valor"]
        saldo += v
        if saldo >= 0:
            return int(t)  # meses até payback
    return None

def _tir(fluxo: pd.DataFrame, data_base: date) -> float | None:
    if fluxo.empty:
        return None
    fluxo = fluxo.sort_values("competencia").copy()
    meses = ((pd.to_datetime(fluxo["competencia"]) - pd.to_datetime(data_base)).dt.days // 30).astype(int)
    max_m = int(meses.max()) if len(meses) else 0
    serie = np.zeros(max_m + 1)
    for m, v in zip(meses, fluxo["valor"]):
        serie[m] += v
    try:
        # Nota: np.irr foi movido para numpy_financial em alguns ambientes;
        # se necessário, troque para numpy_financial.irr
        irr = np.irr(serie)
        if irr is None:
            return None
        return float((1 + irr) ** 12 - 1)  # anualiza
    except Exception:
        return None

# ──────────────────────────────────────────────────────────────────────────────
# UI principal

def aba_financeiro_projeto(usuario_logado: str, nome_usuario: str):
    st.title("💵 Financeiro do Projeto — Fluxo, VPL, Payback e TIR")

    # 🔗 Vincula ao cadastro oficial (projeto obrigatório; atividade opcional aqui)
    seletor_contexto(show_atividade=False, obrigatorio=True)
    projeto_ctx = st.session_state["ctx_projeto"]

    tab1, tab2, tab3 = st.tabs(["⚙️ Parâmetros", "🧾 Lançamentos", "📈 Análises"])

    # ── Parâmetros
    with tab1:
        dfp = _load_params()
        st.subheader("Parâmetros por Projeto")
        if not dfp.empty:
            st.dataframe(dfp, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum parâmetro cadastrado ainda.")

        with st.expander("Adicionar/Editar Parâmetros"):
            projetos_existentes = list_projetos(load_df_atividades())
            if not projetos_existentes:
                st.warning("Cadastre projetos em 🗂️ Projetos e Atividades antes de definir parâmetros financeiros.")
                st.stop()

            # Projeto vem do contexto, mas permitimos trocar entre os válidos
            idx_proj = projetos_existentes.index(projeto_ctx) if projeto_ctx in projetos_existentes else 0
            projeto = st.selectbox("Projeto", options=projetos_existentes, index=idx_proj)

            col1, col2, col3 = st.columns(3)
            taxa = col1.number_input("Taxa de desconto anual (WACC)", min_value=0.0, max_value=1.0, value=0.15, step=0.01, format="%.2f")
            horizonte = col2.number_input("Horizonte (meses)", min_value=12, max_value=240, value=60, step=1)
            data_base = col3.date_input("Data base", value=date(date.today().year, date.today().month, 1))

            col4, col5, col6 = st.columns(3)
            inflacao = col4.number_input("Inflação anual (opcional)", min_value=0.0, max_value=1.0, value=0.0, step=0.01, format="%.2f")
            moeda = col5.text_input("Moeda", value="BRL")
            cenario = col6.selectbox("Cenário", CENARIOS, index=0)

            obs = st.text_area("Observações", placeholder="Premissas, fontes, etc.")

            if st.button("Salvar parâmetros", type="primary"):
                ok, msg = validar_projeto_atividade_valido(projeto)
                if not ok:
                    st.error(msg)
                    st.stop()

                # upsert
                if (dfp["projeto"] == projeto).any():
                    dfp.loc[dfp["projeto"] == projeto, [
                        "taxa_desconto_anual","horizonte_meses","data_base","indice_inflacao_anual","moeda","cenario","observacoes","atualizado_em"
                    ]] = [taxa, int(horizonte), data_base, inflacao, moeda, cenario, obs, datetime.now().isoformat(timespec="seconds")]
                else:
                    dfp = pd.concat([dfp, pd.DataFrame([{
                        "projeto": projeto, "taxa_desconto_anual": taxa, "horizonte_meses": int(horizonte),
                        "data_base": data_base, "indice_inflacao_anual": inflacao, "moeda": moeda, "cenario": cenario,
                        "observacoes": obs, "atualizado_em": datetime.now().isoformat(timespec="seconds")
                    }])], ignore_index=True)

                _save_params(dfp)
                st.success("Parâmetros salvos.")
                st.rerun()

    # ── Lançamentos
    with tab2:
        dfl = _load_lanc()
        st.subheader(f"Lançamentos (Receitas & Despesas) — Projeto: **{projeto_ctx}**")
        if not dfl.empty:
            st.dataframe(
                dfl[dfl["projeto"] == projeto_ctx][[
                    "id","projeto","tipo","categoria","descricao","valor","data_inicio","periodicidade","parcelas",
                    "eh_estimativa","confianca","cenario","capex_opex","fornecedor","centro_custo"
                ]].sort_values(["data_inicio"]).reset_index(drop=True),
                use_container_width=True, hide_index=True
            )
        else:
            st.caption("Nenhum lançamento cadastrado ainda.")

        st.markdown("---")
        st.subheader("➕ Novo lançamento")
        with st.form("form_lanc"):
            # Projeto travado no contexto
            st.caption(f"Projeto: **{projeto_ctx}** (definido no seletor do topo)")

            col1, col2, col3 = st.columns([2,1,1])
            categoria = col1.text_input("Categoria", placeholder="Ex.: Licenças, Serviços, Receita de venda")
            valor = col2.number_input("Valor (positivo)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
            capex_opex = col3.selectbox("CAPEX/OPEX", CAPEX_OPEX)

            col4, col5, col6 = st.columns(3)
            data_inicio = col4.date_input("Data início", value=date.today())
            periodicidade = col5.selectbox("Periodicidade", PERIODICIDADES, index=1)
            parcelas = col6.number_input("Parcelas/Qtd", min_value=1, max_value=240, value=12)

            col7, col8, col9 = st.columns(3)
            tipo = col7.selectbox("Tipo", TIPOS)
            eh_estimativa = col8.checkbox("É estimativa?", value=True)
            confianca = col9.slider("Confiança da estimativa", 0.0, 1.0, 0.7, 0.05)

            col10, col11 = st.columns(2)
            cenario = col10.selectbox("Cenário", CENARIOS, index=0)
            fornecedor = col11.text_input("Fornecedor (opcional)")

            col12, col13 = st.columns(2)
            cc = col12.text_input("Centro de Custo (opcional)")
            descricao = col13.text_input("Descrição (opcional)", placeholder="Detalhes do lançamento")

            submitted = st.form_submit_button("Salvar lançamento")

        if submitted:
            projeto = projeto_ctx  # sempre o contexto atual
            ok, msg = validar_projeto_atividade_valido(projeto)
            if not ok:
                st.error(msg)
                st.stop()
            if valor <= 0:
                st.error("Informe um valor positivo.")
                st.stop()

            novo = {
                "id": str(uuid.uuid4()), "projeto": projeto, "tipo": tipo, "categoria": categoria.strip(),
                "descricao": descricao.strip(), "valor": float(valor), "data_inicio": data_inicio,
                "periodicidade": periodicidade, "parcelas": int(parcelas), "eh_estimativa": bool(eh_estimativa),
                "confianca": float(confianca), "cenario": cenario, "capex_opex": capex_opex, "fornecedor": fornecedor.strip(),
                "centro_custo": cc.strip(), "criado_em": datetime.now().isoformat(timespec="seconds"),
                "atualizado_em": datetime.now().isoformat(timespec="seconds")
            }
            dfl = pd.concat([dfl, pd.DataFrame([novo])], ignore_index=True)
            _save_lanc(dfl)
            st.success("Lançamento salvo.")
            st.rerun()

        with st.expander("✏️ Editar / 🗑️ Excluir"):
            dfl = _load_lanc()
            dfl_proj = dfl[dfl["projeto"] == projeto_ctx].copy()
            if dfl_proj.empty:
                st.caption("Nenhum lançamento deste projeto para editar/excluir.")
            else:
                ids = st.multiselect("Selecione IDs", dfl_proj["id"].tolist())
                colE1, colE2 = st.columns(2)
                if colE1.button("Excluir selecionados", disabled=not ids):
                    dfl = dfl[~dfl["id"].isin(ids)].copy()
                    _save_lanc(dfl)
                    st.success("Excluídos.")
                    st.rerun()
                if colE2.button("Limpar tudo do projeto (cuidado)"):
                    dfl = dfl[dfl["projeto"] != projeto_ctx].copy()
                    _save_lanc(dfl)
                    st.success("Base de lançamentos do projeto limpa.")
                    st.rerun()

    # ── Análises
    with tab3:
        dfp = _load_params()
        dfl = _load_lanc()

        # parâmetros do projeto (se não houver, usamos defaults)
        if (not dfp.empty) and (dfp["projeto"] == projeto_ctx).any():
            linha = dfp[dfp["projeto"] == projeto_ctx].iloc[0].to_dict()
        else:
            linha = {
                "taxa_desconto_anual": 0.15,
                "horizonte_meses": 60,
                "data_base": date(date.today().year, date.today().month, 1),
                "indice_inflacao_anual": 0.0,
                "cenario": "Base",
                "moeda": "BRL",
            }

        fluxo = _expandir_fluxo(dfl, projeto_ctx, linha)
        if fluxo.empty:
            st.warning("Sem fluxo gerado para o projeto selecionado. Cadastre lançamentos na aba anterior.")
            return

        st.subheader(f"Fluxo de Caixa (Mensal) — Projeto: **{projeto_ctx}**")
        fluxo_show = fluxo.copy()
        fluxo_show["competencia"] = pd.to_datetime(fluxo_show["competencia"]).dt.strftime("%Y-%m")
        st.dataframe(fluxo_show, use_container_width=True, hide_index=True)

        colA, colB, colC, colD = st.columns(4)
        vpl = _npv(fluxo, float(linha["taxa_desconto_anual"]), linha["data_base"])
        pb_simples = _payback(fluxo, False, float(linha["taxa_desconto_anual"]), linha["data_base"])
        pb_desc = _payback(fluxo, True, float(linha["taxa_desconto_anual"]), linha["data_base"])
        tir = _tir(fluxo, linha["data_base"])

        colA.metric("VPL (NPV)", f"{vpl:,.2f} {linha['moeda']}")
        colB.metric("Payback (meses)", pb_simples if pb_simples is not None else "N/A")
        colC.metric("Payback Descontado (meses)", pb_desc if pb_desc is not None else "N/A")
        colD.metric("TIR (a.a.)", f"{tir*100:,.2f}%" if tir is not None else "N/A")

        with st.expander("🎯 Sensibilidade (what-if)"):
            colS1, colS2, colS3 = st.columns(3)
            delta_taxa = colS1.number_input("Δ Taxa de Desconto (p.p.)", value=2.0, step=0.5)
            mult_receita = colS2.number_input("Multiplicador de Receitas", value=1.0, step=0.1)
            mult_despesa = colS3.number_input("Multiplicador de Despesas", value=1.0, step=0.1)
            if st.button("Aplicar sensibilidade"):
                dfl2 = _load_lanc()
                dfl2 = dfl2.copy()
                # aplica multiplicadores por tipo
                dfl2.loc[(dfl2["projeto"] == projeto_ctx) & (dfl2["tipo"] == "Receita"), "valor"] *= mult_receita
                dfl2.loc[(dfl2["projeto"] == projeto_ctx) & (dfl2["tipo"] == "Despesa"), "valor"] *= mult_despesa
                fluxo_sens = _expandir_fluxo(dfl2, projeto_ctx, linha)
                vpl_sens = _npv(fluxo_sens, float(linha["taxa_desconto_anual"]) + (delta_taxa/100.0), linha["data_base"])
                st.info(f"VPL sensível: {vpl_sens:,.2f} {linha['moeda']}")

        st.caption("Notas: VPL usa taxa efetiva mensal derivada da taxa anual informada; payback descontado considera a mesma taxa. Valores de despesa entram negativos. Projeto e lançamentos são vinculados ao cadastro oficial.")
