import streamlit as st
import pandas as pd
from datetime import date
import uuid
import plotly.express as px
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

ARQUIVO_RISCOS = "riscos.xlsx"

def _gerar_id():
    return str(uuid.uuid4())

def _nivel_risco(prob, impacto):
    return int(prob) * int(impacto)

def _padronizar_colunas(df):
    colunas = [
        "ID", "Risco", "Categoria", "Probabilidade (1-5)", "Impacto (1-5)",
        "Nível de Risco", "Plano de Mitigação", "Plano de Contingência",
        "Responsável", "Prazo"
    ]
    for c in colunas:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    if not df.empty:
        df["Probabilidade (1-5)"] = pd.to_numeric(df["Probabilidade (1-5)"], errors="coerce")
        df["Impacto (1-5)"] = pd.to_numeric(df["Impacto (1-5)"], errors="coerce")
        df["Nível de Risco"] = pd.to_numeric(df["Nível de Risco"], errors="coerce")
        df["Prazo"] = pd.to_datetime(df["Prazo"], errors="coerce").dt.date
    return df[colunas]

def _carregar_base():
    df = carregar_arquivo_excel(ARQUIVO_RISCOS)
    if df is None or df.empty:
        df = pd.DataFrame(columns=[
            "ID", "Risco", "Categoria", "Probabilidade (1-5)", "Impacto (1-5)",
            "Nível de Risco", "Plano de Mitigação", "Plano de Contingência",
            "Responsável", "Prazo"
        ])
    return _padronizar_colunas(df)

def _salvar_base(df):
    df = _padronizar_colunas(df)
    salvar_arquivo_excel(df, ARQUIVO_RISCOS)

def cadastro_riscos():
    st.header("⚠️ Cadastro de Riscos")

    # ========================
    # FORMULÁRIO DE CADASTRO
    # ========================
    with st.form("form_risco"):
        risco = st.text_input("Descrição do Risco")
        categoria = st.selectbox("Categoria", ["Operacional", "Financeiro", "Técnico", "Regulatório", "Outro"])
        col1, col2 = st.columns([2, 2])
        with col1:
            prob = st.slider("Probabilidade (1 = baixa, 5 = alta)", 1, 5, 3)
            impacto = st.slider("Impacto (1 = baixo, 5 = alto)", 1, 5, 3)
        with col2:
            responsavel = st.text_input("Responsável")
            prazo = st.date_input("Prazo", value=date.today())

        plano_mitigacao = st.text_area("Plano de Mitigação")
        plano_contingencia = st.text_area("Plano de Contingência")

        submit = st.form_submit_button("💾 Cadastrar Risco")
        if submit:
            if not risco or not responsavel:
                st.warning("⚠️ Preencha ao menos a descrição do risco e o responsável.")
            else:
                df = _carregar_base()
                novo = pd.DataFrame([{
                    "ID": _gerar_id(),
                    "Risco": risco.strip(),
                    "Categoria": categoria,
                    "Probabilidade (1-5)": int(prob),
                    "Impacto (1-5)": int(impacto),
                    "Nível de Risco": _nivel_risco(prob, impacto),
                    "Plano de Mitigação": plano_mitigacao.strip(),
                    "Plano de Contingência": plano_contingencia.strip(),
                    "Responsável": responsavel.strip(),
                    "Prazo": prazo
                }])
                df = pd.concat([df, novo], ignore_index=True)
                _salvar_base(df)
                st.success("✅ Risco cadastrado com sucesso!")
                st.experimental_rerun()

    st.markdown("---")

    # ========================
    # LISTA + FILTROS
    # ========================
    df = _carregar_base()
    st.subheader("🔍 Filtros")
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        filtro_categoria = st.selectbox("Categoria", ["Todas"] + df["Categoria"].dropna().unique().tolist())
    with colf2:
        filtro_prob = st.selectbox("Probabilidade mínima", [1, 2, 3, 4, 5], index=0)
    with colf3:
        filtro_impacto = st.selectbox("Impacto mínimo", [1, 2, 3, 4, 5], index=0)

    df_view = df.copy()
    if filtro_categoria != "Todas":
        df_view = df_view[df_view["Categoria"] == filtro_categoria]
    df_view = df_view[df_view["Probabilidade (1-5)"] >= filtro_prob]
    df_view = df_view[df_view["Impacto (1-5)"] >= filtro_impacto]

    st.subheader(f"📋 Riscos encontrados: {len(df_view)}")
    st.dataframe(df_view, use_container_width=True)

    # ========================
    # MAPA DE CALOR
    # ========================
    if not df_view.empty:
        st.subheader("🗺️ Mapa de Riscos (Probabilidade x Impacto)")
        fig = px.scatter(
            df_view,
            x="Impacto (1-5)",
            y="Probabilidade (1-5)",
            size="Nível de Risco",
            color="Nível de Risco",
            hover_data=["Risco", "Categoria", "Responsável", "Prazo", "Plano de Mitigação", "Plano de Contingência"],
            color_continuous_scale="Reds",
            title=None
        )
        fig.update_layout(xaxis_title="Impacto", yaxis_title="Probabilidade", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ========================
    # EDIÇÃO
    # ========================
    st.subheader("✏️ Editar Risco")
    if df.empty:
        st.info("Não há riscos cadastrados.")
    else:
        id_sel = st.selectbox("Selecione o ID", df["ID"].tolist())
        linha = df[df["ID"] == id_sel].iloc[0]

        risco_edit = st.text_input("Descrição do Risco", value=linha["Risco"])
        categoria_edit = st.selectbox("Categoria", ["Operacional", "Financeiro", "Técnico", "Regulatório", "Outro"], index=["Operacional", "Financeiro", "Técnico", "Regulatório", "Outro"].index(linha["Categoria"]) if pd.notnull(linha["Categoria"]) else 0)
        col1, col2 = st.columns(2)
        with col1:
            prob_edit = st.slider("Probabilidade", 1, 5, int(linha["Probabilidade (1-5)"]))
            impacto_edit = st.slider("Impacto", 1, 5, int(linha["Impacto (1-5)"]))
        with col2:
            resp_edit = st.text_input("Responsável", value=linha["Responsável"])
            prazo_edit = st.date_input("Prazo", value=linha["Prazo"] if pd.notnull(linha["Prazo"]) else date.today())

        mitig_edit = st.text_area("Plano de Mitigação", value=linha["Plano de Mitigação"])
        conting_edit = st.text_area("Plano de Contingência", value=linha["Plano de Contingência"])

        if st.button("💾 Atualizar Risco"):
            df.loc[df["ID"] == id_sel, [
                "Risco", "Categoria", "Probabilidade (1-5)", "Impacto (1-5)", "Nível de Risco",
                "Plano de Mitigação", "Plano de Contingência", "Responsável", "Prazo"
            ]] = [
                risco_edit.strip(),
                categoria_edit,
                int(prob_edit),
                int(impacto_edit),
                _nivel_risco(prob_edit, impacto_edit),
                mitig_edit.strip(),
                conting_edit.strip(),
                resp_edit.strip(),
                prazo_edit
            ]
            _salvar_base(df)
            st.success("✅ Risco atualizado!")
            st.experimental_rerun()

    st.markdown("---")

    # ========================
    # EXCLUSÃO
    # ========================
    st.subheader("🗑️ Excluir Risco")
    if df.empty:
        st.info("Não há riscos para excluir.")
    else:
        id_del = st.selectbox("Selecione o ID para excluir", df["ID"].tolist(), key="del_risco")
        confirmar = st.checkbox("Confirmo exclusão permanente")
        if st.button("🗑️ Excluir") and confirmar:
            df = df[df["ID"] != id_del]
            _salvar_base(df)
            st.success("✅ Risco excluído!")
            st.experimental_rerun()
