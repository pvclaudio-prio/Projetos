import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, time
import uuid
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

ARQUIVO_AGENDA = "agenda.xlsx"

TIPOS = ["Reunião", "Entregável", "Sinalização"]
STATUS = ["Planejado", "Concluído", "Atrasado"]

def _gerar_id():
    return str(uuid.uuid4())

def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    colunas = [
        "ID", "Data", "Hora Início", "Hora Fim", "Tipo", "Projeto",
        "Título", "Descrição", "Responsável", "Status", "Local/Link"
    ]
    for c in colunas:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    if not df.empty:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date
        # normaliza horas para texto HH:MM
        for c in ["Hora Início", "Hora Fim"]:
            df[c] = df[c].astype(str).str[:5]
    return df[colunas]

def _carregar_base() -> pd.DataFrame:
    df = carregar_arquivo_excel(ARQUIVO_AGENDA)
    if df is None or df.empty:
        df = pd.DataFrame(columns=[
            "ID", "Data", "Hora Início", "Hora Fim", "Tipo", "Projeto",
            "Título", "Descrição", "Responsável", "Status", "Local/Link"
        ])
    return _padronizar_colunas(df)

def _salvar_base(df: pd.DataFrame):
    df = _padronizar_colunas(df)
    salvar_arquivo_excel(df, ARQUIVO_AGENDA)

def _monday_of_week(some_date: date) -> date:
    return some_date - timedelta(days=some_date.weekday())

def _format_time_input(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def agenda_semanal():
    st.header("📆 Agenda Semanal")

    # ========= CADASTRO =========
    with st.form("form_agenda"):
        col_top = st.columns([1.2, 1, 1, 1])
        with col_top[0]:
            data_item = st.date_input("Data", value=date.today())
        with col_top[1]:
            hora_ini = st.time_input("Hora Início", value=time(9, 0))
        with col_top[2]:
            hora_fim = st.time_input("Hora Fim", value=time(10, 0))
        with col_top[3]:
            tipo = st.selectbox("Tipo", TIPOS, index=0)

        col_mid = st.columns([1.2, 1, 1])
        with col_mid[0]:
            projeto = st.text_input("Projeto")
        with col_mid[1]:
            responsavel = st.text_input("Responsável")
        with col_mid[2]:
            status = st.selectbox("Status", STATUS, index=0)

        titulo = st.text_input("Título")
        descricao = st.text_area("Descrição")
        local = st.text_input("Local/Link")

        submitted = st.form_submit_button("💾 Adicionar à Agenda")
        if submitted:
            if not titulo or not projeto:
                st.warning("⚠️ Informe ao menos Título e Projeto.")
            else:
                df = _carregar_base()
                novo = pd.DataFrame([{
                    "ID": _gerar_id(),
                    "Data": data_item,
                    "Hora Início": _format_time_input(hora_ini),
                    "Hora Fim": _format_time_input(hora_fim),
                    "Tipo": tipo,
                    "Projeto": projeto.strip(),
                    "Título": titulo.strip(),
                    "Descrição": descricao.strip(),
                    "Responsável": responsavel.strip(),
                    "Status": status,
                    "Local/Link": local.strip()
                }])
                df = pd.concat([df, novo], ignore_index=True)
                _salvar_base(df)
                st.success("✅ Item adicionado!")
                st.experimental_rerun()

    st.markdown("---")

    # ========= FILTROS & VISÃO SEMANAL =========
    df = _carregar_base()

    colf = st.columns([1, 1, 1, 1.2])
    with colf[0]:
        data_ref = st.date_input("Semana de referência", value=_monday_of_week(date.today()))
    with colf[1]:
        projeto_f = st.text_input("Filtrar por Projeto")
    with colf[2]:
        resp_f = st.text_input("Filtrar por Responsável")
    with colf[3]:
        tipo_f = st.selectbox("Filtrar por Tipo", ["Todos"] + TIPOS, index=0)

    semana_ini = _monday_of_week(data_ref)
    semana_fim = semana_ini + timedelta(days=6)

    df_view = df.copy()
    if not df_view.empty:
        df_view = df_view[(df_view["Data"] >= semana_ini) & (df_view["Data"] <= semana_fim)]
        if projeto_f:
            df_view = df_view[df_view["Projeto"].str.contains(projeto_f, case=False, na=False)]
        if resp_f:
            df_view = df_view[df_view["Responsável"].str.contains(resp_f, case=False, na=False)]
        if tipo_f != "Todos":
            df_view = df_view[df_view["Tipo"] == tipo_f]

    st.subheader(f"🗓️ Semana: {semana_ini.strftime('%d/%m/%Y')} — {semana_fim.strftime('%d/%m/%Y')}")
    if df_view.empty:
        st.info("Nenhum item para a semana selecionada.")
    else:
        # Ordenação por dia e horário
        df_view = df_view.sort_values(by=["Data", "Hora Início", "Hora Fim", "Projeto", "Título"])

        # Render “grade” semanal (Seg..Dom)
        dias = [semana_ini + timedelta(days=i) for i in range(7)]
        cols = st.columns(7)
        for idx, dia in enumerate(dias):
            with cols[idx]:
                st.markdown(f"**{dia.strftime('%a (%d/%m)')}**")
                bloco = df_view[df_view["Data"] == dia]
                if bloco.empty:
                    st.caption("—")
                else:
                    for _, row in bloco.iterrows():
                        st.write(
                            f"**{row['Hora Início']}-{row['Hora Fim']}** · {row['Tipo']}  \n"
                            f"{row['Título']}  \n"
                            f"📌 *{row['Projeto']}* · 👤 {row['Responsável']} · {row['Status']}"
                        )
                        if row.get("Local/Link"):
                            st.caption(str(row["Local/Link"]))
                        st.divider()

        st.markdown("### 📋 Itens da Semana (Tabela)")
        st.dataframe(df_view, use_container_width=True)

    st.markdown("---")

    # ========= EDIÇÃO =========
    st.subheader("✏️ Editar Item")
    if df.empty:
        st.info("Não há itens para editar.")
    else:
        id_sel = st.selectbox("ID do item", df["ID"].tolist())
        linha = df[df["ID"] == id_sel].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            data_e = st.date_input("Data", value=linha["Data"] if pd.notnull(linha["Data"]) else date.today())
        with col2:
            h_ini_e = st.time_input(
                "Hora Início",
                value=datetime.strptime(str(linha["Hora Início"] or "09:00"), "%H:%M").time()
            )
        with col3:
            h_fim_e = st.time_input(
                "Hora Fim",
                value=datetime.strptime(str(linha["Hora Fim"] or "10:00"), "%H:%M").time()
            )
        with col4:
            tipo_e = st.selectbox("Tipo", TIPOS, index=TIPOS.index(linha["Tipo"]) if pd.notnull(linha["Tipo"]) and linha["Tipo"] in TIPOS else 0)

        projeto_e = st.text_input("Projeto", value=str(linha["Projeto"] or ""))
        titulo_e = st.text_input("Título", value=str(linha["Título"] or ""))
        desc_e = st.text_area("Descrição", value=str(linha["Descrição"] or ""))
        col5, col6, col7 = st.columns(3)
        with col5:
            resp_e = st.text_input("Responsável", value=str(linha["Responsável"] or ""))
        with col6:
            status_e = st.selectbox("Status", STATUS, index=STATUS.index(linha["Status"]) if pd.notnull(linha["Status"]) and linha["Status"] in STATUS else 0)
        with col7:
            local_e = st.text_input("Local/Link", value=str(linha["Local/Link"] or ""))

        if st.button("💾 Atualizar Item"):
            df.loc[df["ID"] == id_sel, [
                "Data", "Hora Início", "Hora Fim", "Tipo", "Projeto", "Título",
                "Descrição", "Responsável", "Status", "Local/Link"
            ]] = [
                data_e,
                _format_time_input(h_ini_e),
                _format_time_input(h_fim_e),
                tipo_e,
                projeto_e.strip(),
                titulo_e.strip(),
                desc_e.strip(),
                resp_e.strip(),
                status_e,
                local_e.strip()
            ]
            _salvar_base(df)
            st.success("✅ Item atualizado!")
            st.experimental_rerun()

    st.markdown("---")

    # ========= EXCLUSÃO =========
    st.subheader("🗑️ Excluir Item")
    if df.empty:
        st.info("Não há itens para excluir.")
    else:
        id_del = st.selectbox("Selecione o ID para excluir", df["ID"].tolist(), key="del_agenda")
        confirmar = st.checkbox("Confirmo a exclusão permanente")
        if st.button("🗑️ Excluir") and confirmar:
            df = df[df["ID"] != id_del]
            _salvar_base(df)
            st.success("✅ Item excluído!")
            st.experimental_rerun()
