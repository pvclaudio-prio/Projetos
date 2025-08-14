# -*- coding: utf-8 -*-
from __future__ import annotations
import os, uuid
from datetime import datetime, date
from typing import Optional
import pandas as pd

# ============================
# Configurações & Caminhos
# ============================
APP_NAME = "Gestão de Projetos"
BASE_DIR = os.environ.get("APP_DATA_DIR", ".")
ARQ_PROJETOS   = os.path.join(BASE_DIR, "projetos.csv")
ARQ_ATIVIDADES = os.path.join(BASE_DIR, "atividades.csv")
ARQ_FINANCEIRO = os.path.join(BASE_DIR, "financeiro_projeto.csv")
ARQ_PONTOS     = os.path.join(BASE_DIR, "pontos_focais.csv")
ARQ_RISCOS     = os.path.join(BASE_DIR, "riscos.csv")

STATUS_OPCOES = ["Pendente", "Em andamento", "Bloqueada", "Concluída"]
RISCO_SEVERIDADE = ["Baixo", "Médio", "Alto", "Crítico"]
RISCO_PROBABILIDADE = ["Rara", "Improvável", "Possível", "Provável", "Quase certa"]
RISCO_STATUS = ["Aberto", "Em tratamento", "Mitigado", "Encerrado"]

# ============================
# Persistência (CSV + wrappers)
# ============================
def _csv_load(path: str, dtypes: Optional[dict] = None) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=dtypes)
    except Exception:
        return pd.DataFrame()

def _csv_save(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(path, index=False)

# Wrappers externos opcionais (ex.: Google Drive/Sheets)
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
    if nome == "projetos":      return _csv_load(ARQ_PROJETOS)
    if nome == "atividades":    return _csv_load(ARQ_ATIVIDADES)
    if nome == "financeiro":    return _csv_load(ARQ_FINANCEIRO)
    if nome == "pontos_focais": return _csv_load(ARQ_PONTOS)
    if nome == "riscos":        return _csv_load(ARQ_RISCOS)
    return pd.DataFrame()

def save_base(df: pd.DataFrame, nome: str) -> None:
    if _external_save_base:
        try:
            _external_save_base(df, nome)
            return
        except Exception:
            pass
    if nome == "projetos":      _csv_save(df, ARQ_PROJETOS)
    elif nome == "atividades":  _csv_save(df, ARQ_ATIVIDADES)
    elif nome == "financeiro":  _csv_save(df, ARQ_FINANCEIRO)
    elif nome == "pontos_focais": _csv_save(df, ARQ_PONTOS)
    elif nome == "riscos":      _csv_save(df, ARQ_RISCOS)

# ============================
# Utilitários
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

def _sev_to_score(sev: str) -> int:
    return {"Baixo": 1, "Médio": 2, "Alto": 3, "Crítico": 4}.get(sev, 0)

def _prob_to_score(prob: str) -> int:
    return {"Rara": 1, "Improvável": 2, "Possível": 3, "Provável": 4, "Quase certa": 5}.get(prob, 0)

# ============================
# Garantia de Schema
# ============================
def ensure_bases() -> None:
    """Cria/migra as bases mínimas (CSVs) para o app."""
    # PROJETOS
    df_p = load_base("projetos")
    if df_p.empty:
        df_p = pd.DataFrame(columns=["id", "nome_projeto", "escopo", "criado_em", "atualizado_em"])
    else:
        if "id" not in df_p.columns:
            df_p.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_p))])
        if "nome_projeto" not in df_p.columns:
            cand = next((c for c in df_p.columns if c.lower() in {"projeto","nome","project","titulo"}), None)
            if cand: df_p = df_p.rename(columns={cand: "nome_projeto"})
            else:    df_p["nome_projeto"] = ""
        if "escopo" not in df_p.columns:
            if "atividade" in df_p.columns: df_p = df_p.rename(columns={"atividade": "escopo"})
            else: df_p["escopo"] = ""
        for col in ("criado_em","atualizado_em"):
            if col not in df_p.columns: df_p[col] = _now_iso()
    save_base(df_p, "projetos")

    # ATIVIDADES
    df_a = load_base("atividades")
    if df_a.empty:
        df_a = pd.DataFrame(columns=[
            "id","projeto_id","descricao","prazo","status","responsavel","criado_em","atualizado_em"
        ])
    else:
        rename_map = {"atividade":"descricao","responsável":"responsavel","deadline":"prazo","vencimento":"prazo"}
        for k,v in rename_map.items():
            if k in df_a.columns and v not in df_a.columns:
                df_a = df_a.rename(columns={k:v})
        if "id" not in df_a.columns:
            df_a.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_a))])
        for col in ["projeto_id","descricao","prazo","status","responsavel"]:
            if col not in df_a.columns: df_a[col] = "" if col!="prazo" else None
        for col in ("criado_em","atualizado_em"):
            if col not in df_a.columns: df_a[col] = _now_iso()
        if "status" in df_a.columns:
            df_a["status"] = df_a["status"].replace({
                "Aberta":"Pendente","Em Progresso":"Em andamento","Fechada":"Concluída"
            })
    save_base(df_a, "atividades")

    # FINANCEIRO
    df_f = load_base("financeiro")
    if df_f.empty:
        df_f = pd.DataFrame(columns=[
            "id","projeto_id","data","categoria","descricao","valor","tipo","criado_em","atualizado_em"
        ])
    else:
        if "id" not in df_f.columns:
            df_f.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_f))])
        for col in ["projeto_id","data","categoria","descricao","valor","tipo"]:
            if col not in df_f.columns: df_f[col] = ""
        for col in ("criado_em","atualizado_em"):
            if col not in df_f.columns: df_f[col] = _now_iso()
    save_base(df_f, "financeiro")

    # PONTOS FOCAIS
    df_pf = load_base("pontos_focais")
    if df_pf.empty:
        df_pf = pd.DataFrame(columns=[
            "id","projeto_id","nome","email","telefone","funcao","observacoes","criado_em","atualizado_em"
        ])
    else:
        if "id" not in df_pf.columns:
            df_pf.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_pf))])
        for col in ["projeto_id","nome","email","telefone","funcao","observacoes"]:
            if col not in df_pf.columns: df_pf[col] = ""
        for col in ("criado_em","atualizado_em"):
            if col not in df_pf.columns: df_pf[col] = _now_iso()
    save_base(df_pf, "pontos_focais")

    # RISCOS
    df_r = load_base("riscos")
    if df_r.empty:
        df_r = pd.DataFrame(columns=[
            "id","projeto_id","categoria","descricao","severidade","probabilidade",
            "status_tratativa","responsavel","prazo_tratativa","impacto_financeiro","criado_em","atualizado_em"
        ])
    else:
        if "id" not in df_r.columns:
            df_r.insert(0, "id", [str(uuid.uuid4()) for _ in range(len(df_r))])
        for col in ["projeto_id","categoria","descricao","severidade","probabilidade",
                    "status_tratativa","responsavel","prazo_tratativa","impacto_financeiro"]:
            if col not in df_r.columns: df_r[col] = ""
        for col in ("criado_em","atualizado_em"):
            if col not in df_r.columns: df_r[col] = _now_iso()
    save_base(df_r, "riscos")

