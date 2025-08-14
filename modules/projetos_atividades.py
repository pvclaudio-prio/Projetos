import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid

# Utils do projeto (já existentes no seu repo)
from modules.crud_utils import carregar_arquivo_excel, salvar_arquivo_excel

# Caminhos/base
BASE_PATH = "bases/projetos_atividades.xlsx"
SHEET_NAME = "projetos_atividades"

# Esquema padrão da base
COLS = [
    "id",               # uuid4
    "projeto",          # str
    "atividade",        # str
    "responsavel",      # str
    "status",           # str: Planejado, Em Andamento, Concluído, Atrasado, Cancelado
    "prioridade",       # str: Baixa, Média, Alta, Crítica
    "inicio",           # date
    "fim",              # date
    "progresso",        # int 0..100
    "comentarios",      # str
    "criado_por",       # str (username)
    "criado_em",        # datetime iso
    "atualizado_em",    # datetime iso
]

STATUS_OPS = ["Planejado", "Em Andamento", "Concluído", "Atrasado", "Cancelado"]
PRIOR_OPS = ["Baixa", "Média", "Alta", "Crítica"]

@st.cache_data(show_spinner=False)
def _carregar_base_crud() -> pd.DataFrame:
    """Carrega a base a partir do Excel. Se não existir, retorna DataFrame vazio com schema.
    Usa cache para leitura rápida; invalidamos após cada gravação.
    """
    try:
        df = carregar_arquivo_excel(BASE_PATH, sheet_name=SHEET_NAME)
        if df is None or df.empty:
            df = pd.DataFrame(columns=COLS)
    except Exception:
        df = pd.DataFrame(columns=COLS)

    # Garantir colunas e tipos
    for c in COLS:
        if c not in df.columns:
            df[c] = None

    # Normalizações
    if not df.empty:
        # datas
        for c in ["inicio", "fim"]:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
        # progresso
        if "progresso" in df.columns:
            df["progresso"] = pd.to_numeric(df["progresso"], errors="coerce").fillna(0).astype(int)
        # strings
        for c in ["projeto", "atividade", "responsavel", "status", "prioridade", "comentarios", "criado_por"]:
            df[c] = df[c].fillna("").astype(str)
    return df[COLS].copy()


def _salvar_base_crud(df: pd.DataFrame):
    """Persistência transacional com validação mínima.
    - Garante schema
    - Salva via util centralizada
    - Limpa cache de leitura
    """
    # Validar e organizar colunas
    missing = [c for c in COLS if c not in df.columns]
    for c in missing:
        df[c] = None
    df = df[COLS].copy()

    # Conversões
    for c in ["inicio", "fim"]:
        if df[c].dtype != "O":
            df[c] = df[c].astype("O")
        df[c] = df[c].apply(lambda x: x.isoformat() if isinstance(x, (date,)) else (x or ""))
    for c in ["criado_em", "atualizado_em"]:
        df[c] = df[c].fillna("").astype(str)

    salvar_arquivo_excel(df, BASE_PATH, sheet_name=SHEET_NAME)
    _carregar_base_crud.clear()


def _kpis(df: pd.DataFrame):
    total = len(df)
    concl = int((df["status"] == "Concluído").sum())
    andamento = int((df["status"] == "Em Andamento").sum())
    atraso = int((df["status"] == "Atrasado").sum())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Itens", total)
    col2.metric("Concluídos", concl)
    col3.metric("Em Andamento", andamento)
    col4.metric("Atrasados", atraso)

def _filtros(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar.expander("🔎 Filtros", expanded=False):
        f_proj = st.text_input("Projeto contém")
        f_resp = st.text_input("Responsável contém")
        f_status = st.multiselect("Status", STATUS_OPS)
        f_prior = st.multiselect("Prioridade", PRIOR_OPS)

        # ✅ Streamlit não aceita None; usamos um toggle para aplicar o período
        usar_periodo = st.checkbox("Filtrar por período", value=False)
        if usar_periodo:
            # intervalo padrão: mês corrente até hoje
            inicio_padrao = date.today().replace(day=1)
            fim_padrao = date.today()
            di, dfim = st.date_input(
                "Período (início a fim)",
                value=(inicio_padrao, fim_padrao),
                format="YYYY-MM-DD"
            )
        else:
            di, dfim = (None, None)

    out = df.copy()
    if f_proj:
        out = out[out["projeto"].str.contains(f_proj, case=False, na=False)]
    if f_resp:
        out = out[out["responsavel"].str.contains(f_resp, case=False, na=False)]
    if f_status:
        out = out[out["status"].isin(f_status)]
    if f_prior:
        out = out[out["prioridade"].isin(f_prior)]

    # aplica período somente se habilitado e datas válidas
    if usar_periodo and isinstance(di, date) and isinstance(dfim, date):
        out = out[
            (out["inicio"].notna()) & (pd.to_datetime(out["inicio"]) >= pd.to_datetime(di))
        ]
        out = out[
            (out["fim"].notna()) & (pd.to_datetime(out["fim"]) <= pd.to_datetime(dfim))
        ]

    return out

def _form_novo_ou_editar(mode: str, usuario: str, registro: dict | None = None) -> dict | None:
    """Formulário de criação/edição. Retorna o payload salvo ou None."""
    assert mode in {"novo", "editar"}
    default = {
        "projeto": "",
        "atividade": "",
        "responsavel": usuario,
        "status": "Planejado",
        "prioridade": "Média",
        "inicio": date.today(),
        "fim": date.today(),
        "progresso": 0,
        "comentarios": "",
    }
    if registro:
        default.update(registro)
        # normalizar datas quando vierem como string
        for c in ["inicio", "fim"]:
            try:
                default[c] = pd.to_datetime(default[c]).date() if default[c] else None
            except Exception:
                default[c] = None

    with st.form(f"form_{mode}"):
        col1, col2 = st.columns(2)
        projeto = col1.text_input("Projeto", value=default["projeto"], placeholder="Ex.: Integração Teradata")
        atividade = col2.text_input("Atividade", value=default["atividade"], placeholder="Ex.: Modelar Tabelas Fato")

        col3, col4, col5 = st.columns(3)
        responsavel = col3.text_input("Responsável", value=default["responsavel"].strip())
        status = col4.selectbox("Status", STATUS_OPS, index=max(0, STATUS_OPS.index(default["status"]) if default["status"] in STATUS_OPS else 0))
        prioridade = col5.selectbox("Prioridade", PRIOR_OPS, index=max(0, PRIOR_OPS.index(default["prioridade"]) if default["prioridade"] in PRIOR_OPS else 1))

        col6, col7, col8 = st.columns(3)
        inicio = col6.date_input("Início", value=default["inicio"])
        fim = col7.date_input("Fim", value=default["fim"])
        progresso = col8.slider("Progresso %", min_value=0, max_value=100, value=int(default["progresso"]))

        comentarios = st.text_area("Comentários", value=default["comentarios"], height=120)

        submitted = st.form_submit_button("Salvar")

    if not submitted:
        return None

    # Validações simples
    if not projeto.strip():
        st.error("Informe o nome do projeto.")
        return None
    if not atividade.strip():
        st.error("Informe a atividade.")
        return None
    if fim and inicio and fim < inicio:
        st.error("Data de fim não pode ser anterior ao início.")
        return None

    payload = {
        "projeto": projeto.strip(),
        "atividade": atividade.strip(),
        "responsavel": responsavel.strip(),
        "status": status,
        "prioridade": prioridade,
        "inicio": inicio,
        "fim": fim,
        "progresso": int(progresso),
        "comentarios": comentarios.strip(),
    }
    return payload


def _toolbar(df_filt: pd.DataFrame) -> tuple[list[str], str]:
    """Barra de ações e seleção de registros.
    Retorna (ids_selecionados, acao) onde acao in {"novo","editar","excluir","exportar","atualizar"}
    """
    st.write("")
    with st.container():
        col1, col2 = st.columns([3,2])
        with col1:
            ids = st.multiselect(
                "Selecione registros (por ID)", options=df_filt["id"].tolist(),
                format_func=lambda _id: f"{_id} — {df_filt.loc[df_filt['id']==_id, 'atividade'].values[0] if (df_filt['id']==_id).any() else _id}",
                placeholder="Escolha um ou mais itens para editar/excluir"
            )
        with col2:
            colA, colB, colC, colD, colE = st.columns(5)
            acao = None
            if colA.button("➕ Novo", use_container_width=True):
                acao = "novo"
            if colB.button("✏️ Editar", use_container_width=True):
                acao = "editar"
            if colC.button("🗑️ Excluir", use_container_width=True):
                acao = "excluir"
            if colD.button("📤 Exportar", use_container_width=True):
                acao = "exportar"
            if colE.button("🔄 Atualizar", use_container_width=True):
                acao = "atualizar"

    # Atalhos contextuais
    with st.container():
        c1, _, _ = st.columns([1,1,3])
        if c1.button("👥 Abrir Pontos Focais do Projeto", disabled=not ids):
            try:
                sel_id = ids[0]
                projeto_sel = df_filt.loc[df_filt["id"] == sel_id, "projeto"].iloc[0]
                st.session_state["projeto_selecionado"] = str(projeto_sel)
                st.session_state["menu"] = "👥 Pontos Focais"
                st.experimental_rerun()
            except Exception:
                st.warning("Não foi possível identificar o projeto selecionado.")

    return ids, acao


def _tabela(df: pd.DataFrame):
    view = df.copy()
    view["inicio"] = pd.to_datetime(view["inicio"], errors="coerce").dt.date
    view["fim"] = pd.to_datetime(view["fim"], errors="coerce").dt.date
    view = view.sort_values(["projeto", "fim", "prioridade"], ascending=[True, True, False])
    st.dataframe(
        view[[
            "id","projeto","atividade","responsavel","status","prioridade","inicio","fim","progresso","comentarios"
        ]].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )


def aba_projetos_atividades(usuario_logado: str, nome_usuario: str):
    st.title("🗂️ Projetos e Atividades")

    # Carregar base
    df = _carregar_base_crud()

    # KPIs
    _kpis(df)

    # Filtros (sidebar)
    df_filt = _filtros(df)

    # Toolbar e seleção (com atalho p/ pontos focais)
    ids_sel, acao = _toolbar(df_filt)

    # Exibição
    _tabela(df_filt)

    # Ações
    if acao == "novo":
        st.subheader("➕ Novo Registro")
        payload = _form_novo_ou_editar("novo", nome_usuario)
        if payload is not None:
            novo = payload | {
                "id": str(uuid.uuid4()),
                "criado_por": usuario_logado or nome_usuario,
                "criado_em": datetime.now().isoformat(timespec="seconds"),
                "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            }
            df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
            _salvar_base_crud(df)
            st.success("Registro criado com sucesso.")
            st.rerun()

    elif acao == "editar":
        if not ids_sel:
            st.warning("Selecione pelo menos um registro para editar.")
            return
        _id = ids_sel[0]
        registro = df.loc[df["id"] == _id].iloc[0].to_dict()
        st.subheader(f"✏️ Editar Registro — ID {_id}")
        payload = _form_novo_ou_editar("editar", nome_usuario, registro)
        if payload is not None:
            for k, v in payload.items():
                df.loc[df["id"] == _id, k] = v
            df.loc[df["id"] == _id, "atualizado_em"] = datetime.now().isoformat(timespec="seconds")
            _salvar_base_crud(df)
            st.success("Registro atualizado com sucesso.")
            st.rerun()

    elif acao == "excluir":
        if not ids_sel:
            st.warning("Selecione ao menos um registro para excluir.")
            return
        with st.popover("Confirmar exclusão?"):
            st.write(f"Você está prestes a excluir **{len(ids_sel)}** registro(s). Esta ação é irreversível.")
            if st.button("Confirmar exclusão", type="primary"):
                df = df[~df["id"].isin(ids_sel)].copy()
                _salvar_base_crud(df)
                st.success("Registros excluídos com sucesso.")
                st.rerun()

    elif acao == "exportar":
        # Exporta o filtro atual como CSV para download
        export_df = df_filt.copy()
        export_df["inicio"] = pd.to_datetime(export_df["inicio"]).dt.strftime("%Y-%m-%d")
        export_df["fim"] = pd.to_datetime(export_df["fim"]).dt.strftime("%Y-%m-%d")
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar CSV (filtro atual)", data=csv, file_name="projetos_atividades.csv", mime="text/csv")

    elif acao == "atualizar":
        _carregar_base_crud.clear()
        st.experimental_rerun()

    # Rodapé de auditoria leve
    with st.expander("🧾 Colunas e Auditoria"):
        st.write(
            "Esta aba salva em \"bases/projetos_atividades.xlsx\" (planilha 'projetos_atividades'). "
            "Campos de controle: id, criado_por, criado_em, atualizado_em."
        )
        st.code(", ".join(COLS))
