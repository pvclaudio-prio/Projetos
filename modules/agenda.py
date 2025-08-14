import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import uuid

from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel
from modules.core_context import seletor_contexto, validar_projeto_atividade_valido, load_df_atividades, list_atividades

# ──────────────────────────────────────────────────────────────────────────────
# Config da base
BASE_AGENDA = "bases/agenda.xlsx"
SHEET_AGENDA = "agenda"

COLS = [
    "id", "projeto", "atividade", "titulo", "descricao", "responsavel",
    "inicio", "fim", "local", "status", "criado_em", "atualizado_em"
]
STATUS_OPS = ["Planejado", "Confirmado", "Concluído", "Cancelado"]

# ──────────────────────────────────────────────────────────────────────────────
# I/O helpers

@st.cache_data(show_spinner=False)
def _load_agenda() -> pd.DataFrame:
    try:
        df = carregar_arquivo_excel(BASE_AGENDA, sheet_name=SHEET_AGENDA)
        if df is None or df.empty:
            df = pd.DataFrame(columns=COLS)
    except Exception:
        df = pd.DataFrame(columns=COLS)

    # garantir colunas
    for c in COLS:
        if c not in df.columns:
            df[c] = None

    # normalizações
    if not df.empty:
        for c in ["projeto", "atividade", "titulo", "descricao", "responsavel", "local", "status"]:
            df[c] = df[c].fillna("").astype(str)
        for c in ["inicio", "fim"]:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        for c in ["criado_em", "atualizado_em"]:
            df[c] = df[c].fillna("").astype(str)

    # ordenar por início
    if not df.empty and "inicio" in df.columns:
        df = df.sort_values("inicio")

    return df[COLS].copy()

def _save_agenda(df: pd.DataFrame):
    df = df[COLS].copy()
    # serializar datas
    df["inicio"] = df["inicio"].apply(lambda x: pd.to_datetime(x).isoformat() if pd.notna(x) else "")
    df["fim"] = df["fim"].apply(lambda x: pd.to_datetime(x).isoformat() if pd.notna(x) else "")
    df["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_arquivo_excel(df, BASE_AGENDA, sheet_name=SHEET_AGENDA)
    _load_agenda.clear()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de tempo/semana

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday = 0

def _sunday_of(d: date) -> date:
    return _monday_of(d) + timedelta(days=6)

def _range_week(center: date) -> tuple[date, date]:
    start = _monday_of(center)
    end = start + timedelta(days=6)
    return start, end

# ──────────────────────────────────────────────────────────────────────────────
# UI

def _header_semana():
    # estado da semana no session_state
    if "agenda_ref_date" not in st.session_state:
        st.session_state["agenda_ref_date"] = date.today()

    colA, colB, colC, colD = st.columns([1, 2, 2, 1])
    with colA:
        if st.button("◀️ Semana -1"):
            st.session_state["agenda_ref_date"] -= timedelta(days=7)
    with colD:
        if st.button("Semana +1 ▶️"):
            st.session_state["agenda_ref_date"] += timedelta(days=7)

    ref = st.session_state["agenda_ref_date"]
    start, end = _range_week(ref)
    with colB:
        st.write(f"**Semana:** {start.strftime('%d/%m/%Y')} — {end.strftime('%d/%m/%Y')}")
    with colC:
        if st.button("Hoje"):
            st.session_state["agenda_ref_date"] = date.today()

    return start, end

def _tabela_semana(dfw: pd.DataFrame):
    """Exibe a visão semanal agrupada por dia."""
    if dfw.empty:
        st.caption("Sem itens nesta semana.")
        return

    # Formatação e exibição
    df_show = dfw.copy()
    df_show["Dia"] = df_show["inicio"].dt.strftime("%a %d/%m")
    df_show["Início"] = df_show["inicio"].dt.strftime("%H:%M")
    df_show["Fim"] = df_show["fim"].dt.strftime("%H:%M")
    cols = ["Dia", "Início", "Fim", "titulo", "responsavel", "local", "status", "atividade", "descricao", "id"]
    st.dataframe(
        df_show[cols].sort_values(["inicio"]).reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )

def _form_item(mode: str, projeto: str, atividades: list[str], registro: dict | None = None) -> dict | None:
    """Form de criação/edição. Retorna payload ou None."""
    assert mode in {"novo", "editar"}
    defaults = {
        "atividade": "",
        "titulo": "",
        "descricao": "",
        "responsavel": "",
        "inicio": datetime.now().replace(minute=0, second=0, microsecond=0),
        "fim": datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
        "local": "",
        "status": "Planejado",
    }
    if registro:
        defaults.update(registro)
        # normalizar datetimes
        for c in ["inicio", "fim"]:
            try:
                defaults[c] = pd.to_datetime(defaults[c])
            except Exception:
                defaults[c] = datetime.now()

    with st.form(f"form_{mode}_agenda"):
        st.caption(f"Projeto: **{projeto}** (definido no seletor do topo)")
        col1, col2 = st.columns([2, 2])
        atividade = col1.selectbox(
            "Atividade (opcional)",
            options=[""] + atividades,
            index=([""] + atividades).index(defaults.get("atividade","")) if defaults.get("atividade","") in ([""] + atividades) else 0
        )
        titulo = col2.text_input("Título do compromisso", value=defaults["titulo"], placeholder="Ex.: Reunião de kickoff")

        col3, col4 = st.columns(2)
        inicio = col3.datetime_input("Início", value=defaults["inicio"])
        fim = col4.datetime_input("Fim", value=defaults["fim"])

        col5, col6, col7 = st.columns([2, 2, 1])
        responsavel = col5.text_input("Responsável", value=defaults["responsavel"])
        local = col6.text_input("Local/Link", value=defaults["local"])
        status = col7.selectbox("Status", STATUS_OPS, index=max(0, STATUS_OPS.index(defaults["status"]) if defaults["status"] in STATUS_OPS else 0))

        descricao = st.text_area("Descrição/Observações", value=defaults["descricao"], height=100)

        submitted = st.form_submit_button("Salvar")

    if not submitted:
        return None

    # validações
    ok, msg = validar_projeto_atividade_valido(projeto, atividade if atividade else None)
    if not ok:
        st.error(msg)
        return None
    if not titulo.strip():
        st.error("Informe um título para o compromisso.")
        return None
    if pd.to_datetime(fim) <= pd.to_datetime(inicio):
        st.error("A data/hora de fim deve ser após o início.")
        return None

    return {
        "projeto": projeto,
        "atividade": atividade or "",
        "titulo": titulo.strip(),
        "descricao": descricao.strip(),
        "responsavel": responsavel.strip(),
        "inicio": pd.to_datetime(inicio),
        "fim": pd.to_datetime(fim),
        "local": local.strip(),
        "status": status,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Página pública

def agenda_semanal():
    st.title("📆 Agenda do Projeto")

    # 🔗 Vincula ao cadastro oficial (Projeto obrigatório, Atividade opcional)
    seletor_contexto(show_atividade=True, obrigatorio=True)
    projeto = st.session_state["ctx_projeto"]
    atividade_ctx = st.session_state["ctx_atividade"]

    df_ag = _load_agenda()

    # Cabeçalho de semana (com navegação)
    ini_semana, fim_semana = _header_semana()

    # Filtro por projeto/atividade e por semana
    df_view = df_ag[df_ag["projeto"] == projeto].copy()
    if atividade_ctx:
        df_view = df_view[df_view["atividade"] == atividade_ctx]
    df_view = df_view[
        (df_view["inicio"] >= pd.Timestamp(ini_semana)) &
        (df_view["inicio"] < pd.Timestamp(fim_semana) + pd.Timedelta(days=1))
    ].copy()

    st.subheader(f"Semana de {ini_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}")
    _tabela_semana(df_view)

    st.markdown("---")
    st.subheader("➕ Novo compromisso")
    atividades_validas = list_atividades(load_df_atividades(), projeto)
    payload = _form_item("novo", projeto, atividades_validas)
    if payload is not None:
        novo = payload | {
            "id": str(uuid.uuid4()),
            "criado_em": datetime.now().isoformat(timespec="seconds"),
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        }
        df_ag = pd.concat([df_ag, pd.DataFrame([novo])], ignore_index=True)
        _save_agenda(df_ag)
        st.success("Compromisso criado.")
        st.rerun()

    with st.expander("✏️ Editar / 🗑️ Excluir"):
        # Seleciona entre os itens da semana filtrada
        df_sel_src = df_ag[(df_ag["projeto"] == projeto)]
        if atividade_ctx:
            df_sel_src = df_sel_src[df_sel_src["atividade"] == atividade_ctx]
        if df_sel_src.empty:
            st.caption("Nenhum compromisso para editar/excluir.")
        else:
            ids = st.multiselect(
                "Selecione IDs",
                df_sel_src["id"].tolist(),
                format_func=lambda _id: f"{_id} — {df_sel_src.loc[df_sel_src['id']==_id, 'titulo'].values[0] if (df_sel_src['id']==_id).any() else _id}"
            )
            colE1, colE2 = st.columns(2)

            # Edição
            if ids:
                sel_id = ids[0]
                reg = df_sel_src.loc[df_sel_src["id"] == sel_id].iloc[0].to_dict()
                st.write(f"Editando ID: **{sel_id}**")
                atividades_validas = list_atividades(load_df_atividades(), projeto)
                edit_payload = _form_item("editar", projeto, atividades_validas, reg)
                if edit_payload is not None:
                    df_all = _load_agenda()
                    for k, v in edit_payload.items():
                        df_all.loc[df_all["id"] == sel_id, k] = v
                    df_all.loc[df_all["id"] == sel_id, "atualizado_em"] = datetime.now().isoformat(timespec="seconds")
                    _save_agenda(df_all)
                    st.success("Compromisso atualizado.")
                    st.rerun()

            # Exclusão
            if colE1.button("Excluir selecionados", disabled=not ids):
                df_all = _load_agenda()
                df_all = df_all[~df_all["id"].isin(ids)].copy()
                _save_agenda(df_all)
                st.success("Excluídos.")
                st.rerun()

            # Limpar todos do projeto/atividade
            if colE2.button("Limpar todos do projeto/atividade (cuidado)"):
                df_all = _load_agenda()
                mask = df_all["projeto"] == projeto
                if atividade_ctx:
                    mask = mask & (df_all["atividade"] == atividade_ctx)
                df_all = df_all[~mask].copy()
                _save_agenda(df_all)
                st.success("Base da agenda (escopo atual) limpa.")
                st.rerun()
