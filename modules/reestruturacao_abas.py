# -*- coding: utf-8 -*-
"""
MÓDULO: reestruturacao_abas.py
Objetivo:
- Ajustar a aba **Projetos e Atividades** para que o campo de "atividade" registre o **escopo do projeto**.
- Substituir a aba **Ganhos** por uma nova aba **Cadastro de Atividades** (prazo, status, descrição e responsável).
- Integrar as **Atividades** com a **Agenda** para visualizar atividades por data (vencendo, vencidas, concluídas, etc.).

Integração:
- Mantém compatibilidade com armazenamento em CSV local **OU** com funções existentes do app
  (por ex.: Google Drive / Planilhas) via wrappers `load_base` e `save_base`.

Como usar:
1) Importe as funções deste módulo no app principal e substitua as chamadas das abas antigas:
   - `aba_projetos_e_atividades(st)`  (ajustada para ESCOPOS)
   - `aba_cadastro_atividades(st)`    (nova, substitui a antiga "Ganhos")
   - `aba_agenda(st)`                 (mostra calendário/listagens por data)
2) Garanta que `ensure_bases()` seja executada na inicialização do app para criar/ajustar esquemas.

Observação:
- Este módulo não altera a lógica de autenticação do seu app.
- Caso já existam bases com outros nomes/estruturas, o bloco de MIGRAÇÃO tenta ajustar sem perder dados.
"""

from __future__ import annotations
import os
import uuid
from datetime import datetime, date
from typing import Optional, Tuple

import pandas as pd

# ============================
# Configurações / Constantes
# ============================
BASE_DIR = os.environ.get("APP_DATA_DIR", ".")
ARQ_PROJETOS = os.path.join(BASE_DIR, "projetos.csv")
ARQ_ATIVIDADES = os.path.join(BASE_DIR, "atividades.csv")

STATUS_OPCOES = [
    "Pendente",
    "Em andamento",
    "Bloqueada",
    "Concluída",
]

# ======================================================
# Wrappers de persistência (CSV local OU Drive/Sheets)
# ======================================================

def _csv_load(path: str, dtypes: Optional[dict] = None) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=dtypes)
    return df


def _csv_save(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(path, index=False)


# Observação: Caso seu app já tenha funções próprias para carregar/salvar
# (ex.: Google Drive, Planilhas), importe-as e substitua aqui.
# Tente utilizar funções globais do app se existirem.
try:
    from app_storage import load_base as _external_load_base  # type: ignore
    from app_storage import save_base as _external_save_base  # type: ignore
except Exception:
    _external_load_base = None
    _external_save_base = None


def load_base(nome: str) -> pd.DataFrame:
    if _external_load_base:
        try:
            return _external_load_base(nome)
        except Exception:
            pass
    # Fallback CSV
    if nome == "projetos":
        return _csv_load(ARQ_PROJETOS)
    if nome == "atividades":
        return _csv_load(ARQ_ATIVIDADES)
    return pd.DataFrame()


def save_base(df: pd.DataFrame, nome: str) -> None:
    if _external_save_base:
        try:
            _external_save_base(df, nome)
            return
        except Exception:
            pass
    # Fallback CSV
    if nome == "projetos":
        _csv_save(df, ARQ_PROJETOS)
    elif nome == "atividades":
        _csv_save(df, ARQ_ATIVIDADES)


# ============================
# Migração / Garantia de schema
# ============================

def ensure_bases() -> None:
    """Garante a existência das bases e faz migração de colunas.
    - projetos: id, nome_projeto, escopo, criado_em, atualizado_em
    - atividades: id, projeto_id, descricao, prazo (YYYY-MM-DD), status, responsavel, criado_em, atualizado_em
    """
    # PROJETOS
    df_p = load_base("projetos")
    if df_p.empty:
        df_p = pd.DataFrame(
            columns=[
                "id",
                "nome_projeto",
                "escopo",
                "criado_em",
                "atualizado_em",
            ]
        )
    else:
        # Normaliza colunas mínimas
        if "id" not in df_p.columns:
            df_p.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_p))])
        if "nome_projeto" not in df_p.columns:
            # tenta mapear campos comuns
            cand = next((c for c in df_p.columns if c.lower() in {"projeto", "nome", "project", "titulo"}), None)
            if cand:
                df_p = df_p.rename(columns={cand: "nome_projeto"})
            else:
                df_p["nome_projeto"] = ""
        if "escopo" not in df_p.columns:
            # <- Campo chave: ESCOP0 substitui antiga 'atividade' da aba
            # Se havia coluna 'atividade' no antigo layout da aba, migra para 'escopo'
            if "atividade" in df_p.columns:
                df_p = df_p.rename(columns={"atividade": "escopo"})
            else:
                df_p["escopo"] = ""
        for col in ("criado_em", "atualizado_em"):
            if col not in df_p.columns:
                df_p[col] = datetime.utcnow().isoformat()
    save_base(df_p, "projetos")

    # ATIVIDADES
    df_a = load_base("atividades")
    if df_a.empty:
        df_a = pd.DataFrame(
            columns=[
                "id",
                "projeto_id",
                "descricao",
                "prazo",
                "status",
                "responsavel",
                "criado_em",
                "atualizado_em",
            ]
        )
    else:
        # Normalização/migração de nomes
        rename_map = {
            "atividade": "descricao",
            "responsável": "responsavel",
            "deadline": "prazo",
            "vencimento": "prazo",
        }
        for k, v in rename_map.items():
            if k in df_a.columns and v not in df_a.columns:
                df_a = df_a.rename(columns={k: v})
        # Colunas mínimas
        if "id" not in df_a.columns:
            df_a.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_a))])
        for col in ["projeto_id", "descricao", "prazo", "status", "responsavel"]:
            if col not in df_a.columns:
                df_a[col] = "" if col != "prazo" else None
        for col in ("criado_em", "atualizado_em"):
            if col not in df_a.columns:
                df_a[col] = datetime.utcnow().isoformat()
        # Normaliza status para o conjunto padrão
        if "status" in df_a.columns:
            df_a["status"] = df_a["status"].replace({
                "Aberta": "Pendente",
                "Em Progresso": "Em andamento",
                "Fechada": "Concluída",
            })
    save_base(df_a, "atividades")


# ============================
# Helpers
# ============================

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_date(d: Optional[str | date]) -> Optional[date]:
    if d is None or d == "":
        return None
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        try:
            return pd.to_datetime(d).date()
        except Exception:
            return None


# ============================
# ABA: Projetos e (Escopo)
# ============================

def aba_projetos_e_atividades(st):
    """Aba ajustada: registra ESCOP0 do projeto (antes: campo 'atividade')."""
    st.subheader("📁 Projetos & Escopo")
    st.caption("Cadastre seus projetos e detalhe o escopo no campo abaixo.")

    df_p = load_base("projetos").copy()

    with st.expander("➕ Novo projeto", expanded=False):
        nome = st.text_input("Nome do projeto", key="np_nome")
        escopo = st.text_area("Escopo do projeto", key="np_escopo", height=160,
                              help="Descreva objetivos, entregáveis, premissas e restrições.")
        if st.button("Salvar projeto", type="primary", key="np_salvar"):
            if not nome.strip():
                st.error("Informe o nome do projeto.")
            else:
                novo = {
                    "id": str(uuid.uuid4()),
                    "nome_projeto": nome.strip(),
                    "escopo": escopo.strip(),
                    "criado_em": _now_iso(),
                    "atualizado_em": _now_iso(),
                }
                df_p = pd.concat([df_p, pd.DataFrame([novo])], ignore_index=True)
                save_base(df_p, "projetos")
                st.success("Projeto salvo com sucesso.")

    if df_p.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # Lista e edição rápida
    st.write("### Projetos")
    st.dataframe(df_p[["nome_projeto", "escopo", "criado_em"]].rename(
        columns={"nome_projeto": "Projeto", "escopo": "Escopo"}
    ), use_container_width=True)

    st.write("### Editar projeto")
    proj_idx = st.selectbox(
        "Selecione um projeto para editar",
        options=list(range(len(df_p))),
        format_func=lambda i: df_p.loc[i, "nome_projeto"],
        key="ed_proj_idx",
    )
    if proj_idx is not None:
        nome_e = st.text_input("Nome do projeto", value=df_p.loc[proj_idx, "nome_projeto"], key="ed_nome")
        escopo_e = st.text_area("Escopo do projeto", value=df_p.loc[proj_idx, "escopo"], height=160, key="ed_escopo")
        cols = st.columns(2)
        with cols[0]:
            if st.button("Salvar alterações", key="ed_salvar"):
                df_p.loc[proj_idx, "nome_projeto"] = nome_e.strip()
                df_p.loc[proj_idx, "escopo"] = escopo_e.strip()
                df_p.loc[proj_idx, "atualizado_em"] = _now_iso()
                save_base(df_p, "projetos")
                st.success("Projeto atualizado.")
        with cols[1]:
            if st.button("Excluir projeto", key="ed_excluir"):
                pid = df_p.loc[proj_idx, "id"]
                df_p = df_p.drop(index=proj_idx).reset_index(drop=True)
                save_base(df_p, "projetos")
                # Cascata simples: desvincular atividades
                df_a = load_base("atividades")
                if not df_a.empty:
                    df_a = df_a[df_a["projeto_id"] != pid].reset_index(drop=True)
                    save_base(df_a, "atividades")
                st.warning("Projeto excluído e atividades vinculadas removidas.")


# =============================================
# ABA: Cadastro de Atividades (substitui Ganhos)
# =============================================

def aba_cadastro_atividades(st):
    st.subheader("✅ Cadastro de Atividades do Projeto")
    st.caption("Registre atividades com prazo, status, descrição e responsável. Integrado à Agenda.")

    df_p = load_base("projetos").copy()
    df_a = load_base("atividades").copy()

    if df_p.empty:
        st.info("Cadastre um projeto na aba 'Projetos & Escopo' antes de incluir atividades.")
        return

    # Formulário de criação
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

    # Filtros
    cols_f = st.columns(4)
    with cols_f[0]:
        proj_f = st.selectbox(
            "Projeto",
            options=["(Todos)"] + df_p["nome_projeto"].tolist(),
            index=0,
            key="f_proj",
        )
    with cols_f[1]:
        status_f = st.selectbox("Status", ["(Todos)"] + STATUS_OPCOES, index=0, key="f_status")
    with cols_f[2]:
        dt_ini = st.date_input("De (prazo)", value=None, key="f_de")
    with cols_f[3]:
        dt_fim = st.date_input("Até (prazo)", value=None, key="f_ate")

    df_list = df_a.merge(df_p[["id", "nome_projeto"]], left_on="projeto_id", right_on="id", how="left", suffixes=("", "_p"))
    df_list = df_list.rename(columns={"nome_projeto": "Projeto"})
    df_list["Prazo"] = df_list["prazo"].apply(lambda x: _parse_date(x))

    if proj_f != "(Todos)":
        df_list = df_list[df_list["Projeto"] == proj_f]
    if status_f != "(Todos)":
        df_list = df_list[df_list["status"] == status_f]
    if dt_ini:
        df_list = df_list[df_list["Prazo"].fillna(date(2100,1,1)) >= dt_ini]
    if dt_fim:
        df_list = df_list[df_list["Prazo"].fillna(date(1900,1,1)) <= dt_fim]

    vis = df_list[["Projeto", "descricao", "responsavel", "status", "Prazo", "criado_em"]].rename(columns={
        "descricao": "Descrição",
        "responsavel": "Responsável",
        "status": "Status",
        "criado_em": "Criado em",
    }).sort_values(by=["Prazo", "Projeto", "Status"], ascending=[True, True, True])

    st.write("### Atividades")
    st.dataframe(vis, use_container_width=True)

    # Edição rápida
    st.write("### Editar atividade")
    if not df_list.empty:
        # map índice visual -> id
        id_map = df_list["id_x" if "id_x" in df_list.columns else "id"].tolist()
        idx = st.selectbox(
            "Selecione uma atividade",
            options=list(range(len(id_map))),
            format_func=lambda i: f"{df_list.iloc[i]['Projeto']} · {df_list.iloc[i]['descricao'][:40]}",
            key="ed_atv_idx",
        )
        if idx is not None:
            atv_id = id_map[idx]
            row = df_a[df_a["id"] == atv_id].iloc[0]
            # campos editáveis
            proj_sel = df_p.index[df_p["id"] == row["projeto_id"]].tolist()[0]
            proj_e = st.selectbox(
                "Projeto",
                options=list(range(len(df_p))),
                index=proj_sel,
                format_func=lambda i: df_p.loc[i, "nome_projeto"],
                key="ed_atv_proj",
            )
            desc_e = st.text_area("Descrição", value=row["descricao"], key="ed_atv_desc")
            prazo_e = st.date_input("Prazo", value=_parse_date(row["prazo"]) or date.today(), key="ed_atv_prazo")
            status_e = st.selectbox("Status", STATUS_OPCOES, index=max(0, STATUS_OPCOES.index(row["status"]) if row["status"] in STATUS_OPCOES else 0), key="ed_atv_status")
            resp_e = st.text_input("Responsável", value=row.get("responsavel", ""), key="ed_atv_resp")
            cols_b = st.columns(2)
            with cols_b[0]:
                if st.button("Salvar alterações", key="ed_atv_salvar"):
                    df_a.loc[df_a["id"] == atv_id, [
                        "projeto_id", "descricao", "prazo", "status", "responsavel", "atualizado_em"
                    ]] = [
                        df_p.loc[proj_e, "id"],
                        desc_e.strip(),
                        _parse_date(prazo_e).strftime("%Y-%m-%d") if prazo_e else None,
                        status_e,
                        resp_e.strip(),
                        _now_iso(),
                    ]
                    save_base(df_a, "atividades")
                    st.success("Atividade atualizada.")
            with cols_b[1]:
                if st.button("Excluir atividade", key="ed_atv_excluir"):
                    df_a = df_a[df_a["id"] != atv_id].reset_index(drop=True)
                    save_base(df_a, "atividades")
                    st.warning("Atividade excluída.")


# ============================
# ABA: Agenda (integração)
# ============================

def aba_agenda(st):
    st.subheader("🗓️ Agenda de Atividades")
    st.caption("Visualize atividades por data de vencimento e status.")

    df_p = load_base("projetos").copy()
    df_a = load_base("atividades").copy()

    if df_a.empty:
        st.info("Nenhuma atividade cadastrada.")
        return

    df = df_a.merge(df_p[["id", "nome_projeto"]], left_on="projeto_id", right_on="id", how="left", suffixes=("", "_p"))
    df = df.rename(columns={"nome_projeto": "Projeto"})
    df["Prazo"] = df["prazo"].apply(_parse_date)

    # Indicadores
    hoje = date.today()
    df["Status_simplificado"] = df["status"].replace({"Concluída": "Concluída"}).apply(lambda s: s if s == "Concluída" else "Aberta")
    total = len(df)
    vencidas = len(df[(df["Status_simplificado"] == "Aberta") & (df["Prazo"].notna()) & (df["Prazo"] < hoje)])
    vencendo_hoje = len(df[(df["Status_simplificado"] == "Aberta") & (df["Prazo"] == hoje)])
    futuras = len(df[(df["Status_simplificado"] == "Aberta") & (df["Prazo"].notna()) & (df["Prazo"] > hoje)])
    concluidas = len(df[df["Status_simplificado"] == "Concluída"])

    cols = st.columns(4)
    cols[0].metric("Total", total)
    cols[1].metric("Vencidas", vencidas)
    cols[2].metric("Vencem hoje", vencendo_hoje)
    cols[3].metric("Futuras", futuras)

    # Filtros
    st.write("### Filtros")
    cols_f = st.columns(4)
    with cols_f[0]:
        proj = st.selectbox("Projeto", ["(Todos)"] + sorted(df["Projeto"].dropna().unique().tolist()))
    with cols_f[1]:
        resp = st.selectbox("Responsável", ["(Todos)"] + sorted(df["responsavel"].fillna("").unique().tolist()))
    with cols_f[2]:
        mostrar_concluidas = st.toggle("Incluir concluídas", value=False)
    with cols_f[3]:
        janela = st.slider("Janela (dias a partir de hoje)", min_value=0, max_value=90, value=30)

    base = df.copy()
    if proj != "(Todos)":
        base = base[base["Projeto"] == proj]
    if resp != "(Todos)":
        base = base[base["responsavel"] == resp]
    if not mostrar_concluidas:
        base = base[base["status"] != "Concluída"]

    fim = date.today().toordinal() + janela
    base = base[base["Prazo"].notna()]
    base = base[base["Prazo"].apply(lambda d: d.toordinal() <= fim)]

    # Agenda por data
    agenda = base.groupby("Prazo").agg({"descricao": "count"}).rename(columns={"descricao": "Qtd"}).reset_index()
    agenda = agenda.sort_values("Prazo")

    st.write("### Atividades por data")
    st.dataframe(agenda.rename(columns={"Prazo": "Data"}), use_container_width=True)

    # Detalhes do dia selecionado
    dia = st.date_input("Ver detalhes do dia", value=date.today())
    detal = base[base["Prazo"] == dia]
    if detal.empty:
        st.info("Sem atividades na data selecionada.")
    else:
        st.write(f"### Atividades em {dia.strftime('%d/%m/%Y')}")
        st.dataframe(
            detal[["Projeto", "descricao", "responsavel", "status", "Prazo"]]
            .rename(columns={"descricao": "Descrição", "responsavel": "Responsável"})
            .sort_values(["status", "Projeto", "Descrição"]),
            use_container_width=True,
        )


# ============================
# Hook de inicialização
# ============================

def inicializar_modulo() -> None:
    ensure_bases()


if __name__ == "__main__":
    # Para testes locais (fora do Streamlit), apenas garante/mostra bases.
    ensure_bases()
    print("Bases garantidas em:", BASE_DIR)
