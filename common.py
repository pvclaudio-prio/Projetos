# -*- coding: utf-8 -*-
from __future__ import annotations
import os, uuid
from datetime import datetime, date
from typing import Optional, Dict
import pandas as pd

# =========================================================
# Configurações & Caminhos
# =========================================================
APP_NAME = "Gestão de Projetos"
BASE_DIR = os.environ.get("APP_DATA_DIR", "./data_excel")

# Fallback local (Excel)
XLSX_PROJETOS   = os.path.join(BASE_DIR, "projetos.xlsx")
XLSX_ATIVIDADES = os.path.join(BASE_DIR, "atividades.xlsx")
XLSX_FINANCEIRO = os.path.join(BASE_DIR, "financeiro_projeto.xlsx")
XLSX_PONTOS     = os.path.join(BASE_DIR, "pontos_focais.xlsx")
XLSX_RISCOS     = os.path.join(BASE_DIR, "riscos.xlsx")

# Compat: CSV legado (apenas leitura se existir)
CSV_PROJETOS   = os.path.join(BASE_DIR, "projetos.csv")
CSV_ATIVIDADES = os.path.join(BASE_DIR, "atividades.csv")
CSV_FINANCEIRO = os.path.join(BASE_DIR, "financeiro_projeto.csv")
CSV_PONTOS     = os.path.join(BASE_DIR, "pontos_focais.csv")
CSV_RISCOS     = os.path.join(BASE_DIR, "riscos.csv")

STATUS_OPCOES = ["Pendente", "Em andamento", "Bloqueada", "Concluída"]
RISCO_SEVERIDADE = ["Baixo", "Médio", "Alto", "Crítico"]
RISCO_PROBABILIDADE = ["Rara", "Improvável", "Possível", "Provável", "Quase certa"]
RISCO_STATUS = ["Aberto", "Em tratamento", "Mitigado", "Encerrado"]

# =========================================================
# Integração com Streamlit (cache) + wrappers externos
# =========================================================
try:
    import streamlit as st
except Exception:  # caso rode fora do Streamlit (tests/scripts)
    class _Dummy:
        cache_data = None
        cache_resource = None
        session_state = {}
    st = _Dummy()  # type: ignore

# Wrappers externos opcionais (Drive/Sheets/Excel via app_storage.py)
try:
    from app_storage import load_base as _external_load_base  # type: ignore
    from app_storage import save_base as _external_save_base  # type: ignore
except Exception:
    _external_load_base = None  # type: ignore
    _external_save_base = None  # type: ignore

_XLSX_MAP: Dict[str, str] = {
    "projetos": XLSX_PROJETOS,
    "atividades": XLSX_ATIVIDADES,
    "financeiro": XLSX_FINANCEIRO,
    "pontos_focais": XLSX_PONTOS,
    "riscos": XLSX_RISCOS,
}
_CSV_MAP: Dict[str, str] = {
    "projetos": CSV_PROJETOS,
    "atividades": CSV_ATIVIDADES,
    "financeiro": CSV_FINANCEIRO,
    "pontos_focais": CSV_PONTOS,
    "riscos": CSV_RISCOS,
}

# =========================================================
# Helpers de IO local
# =========================================================
def _xlsx_load(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_excel(path)
    except Exception:
        return pd.DataFrame()

def _xlsx_save(df: pd.DataFrame, path: str, sheet_name: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        (df if isinstance(df, pd.DataFrame) else pd.DataFrame())\
            .to_excel(writer, index=False, sheet_name=sheet_name[:31])

def _csv_load(path: str, dtypes: Optional[dict] = None) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=dtypes)
    except Exception:
        return pd.DataFrame()

# =========================================================
# Cache inteligente (carregamento rápido com invalidação por base)
# =========================================================
def _get_revs():
    """Contador de revisão por base (para invalidar cache seletivamente)."""
    if getattr(st, "session_state", None) is not None:
        st.session_state.setdefault("_data_revs", {})
        return st.session_state["_data_revs"]
    # fallback fora de sessão
    if not hasattr(_get_revs, "_mem"):
        _get_revs._mem = {}
    return _get_revs._mem  # type: ignore[attr-defined]

# ---- Overrides de fonte (priorizar external|local conforme sucesso do save) ----
def _get_source_overrides():
    """Mantém overrides por base: 'external' | 'local'."""
    if getattr(st, "session_state", None) is not None:
        st.session_state.setdefault("_data_source_override", {})
        return st.session_state["_data_source_override"]
    if not hasattr(_get_source_overrides, "_mem"):
        _get_source_overrides._mem = {}
    return _get_source_overrides._mem  # type: ignore[attr-defined]

def _set_source_override(nome: str, prefer: Optional[str]):
    ovs = _get_source_overrides()
    if prefer is None:
        ovs.pop(nome, None)
    else:
        ovs[nome] = prefer

def _rough_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Comparação leve para validar pós-gravação."""
    if a.shape != b.shape:
        return False
    try:
        return a.head(50).reset_index(drop=True).fillna("").equals(
            b.head(50).reset_index(drop=True).fillna("")
        )
    except Exception:
        return False

# =========================================================
# Loader com prioridade dinâmica (external vs local) + cache opcional
# =========================================================
def _load_base_cached_impl(nome: str, rev: int) -> pd.DataFrame:  # noqa: ARG001
    prefer = _get_source_overrides().get(nome)  # 'external' | 'local' | None

    def _load_external() -> pd.DataFrame:
        if _external_load_base:
            try:
                df = _external_load_base(nome)  # type: ignore
                if isinstance(df, pd.DataFrame):
                    return df
            except Exception:
                pass
        return pd.DataFrame()

    def _load_local() -> pd.DataFrame:
        path = _XLSX_MAP.get(nome)
        if path:
            df = _xlsx_load(path)
            if not df.empty:
                return df
        path = _CSV_MAP.get(nome)
        if path:
            df = _csv_load(path)
            if not df.empty:
                return df
        return pd.DataFrame()

    # Ordem de prioridade conforme override
    loaders = [_load_external, _load_local] if prefer != "local" else [_load_local, _load_external]

    for fn in loaders:
        df = fn()
        if not df.empty:
            return df
    return pd.DataFrame()

# Mantém o comportamento de cache se disponível
if getattr(st, "cache_data", None):
    @st.cache_data(show_spinner=False)
    def _load_base_cached(nome: str, rev: int) -> pd.DataFrame:
        return _load_base_cached_impl(nome, rev)
else:
    def _load_base_cached(nome: str, rev: int) -> pd.DataFrame:
        return _load_base_cached_impl(nome, rev)

def load_base(nome: str) -> pd.DataFrame:
    revs = _get_revs()
    rev = int(revs.get(nome, 0))
    return _load_base_cached(nome, rev)

def load_base_fresh(nome: str) -> pd.DataFrame:
    """Força recarregar ignorando cache atual (incrementa rev)."""
    revs = _get_revs()
    revs[nome] = int(revs.get(nome, 0)) + 1
    return _load_base_cached(nome, revs[nome])

# =========================================================
# Save com validação do backend externo + fallback local explícito
# =========================================================
def save_base(df: pd.DataFrame, nome: str) -> None:
    """
    Salva a base. Estratégia:
    1) Tenta salvar no backend externo (Drive/Sheets), se existir;
       - Relê do externo e valida. Se falhar, informa erro.
    2) Salva SEMPRE uma cópia local em Excel (backup).
    3) Invalida cache (rev++).
    4) Define prioridade de leitura:
       - Se externo OK -> prefer 'external'
       - Se externo falhou -> prefer 'local' (até próxima gravação bem-sucedida)
    """
    external_ok = False
    external_error: Optional[Exception] = None

    # 1) Tenta salvar no externo (Drive/Sheets/etc.)
    if _external_save_base:
        try:
            _external_save_base(df, nome)  # type: ignore
            # valida: reler do externo e comparar de forma leve
            if _external_load_base:
                df_check = _external_load_base(nome)  # type: ignore
                if isinstance(df_check, pd.DataFrame) and not df_check.empty:
                    if _rough_equal(df, df_check) or len(df_check) == len(df):
                        external_ok = True
                    else:
                        raise RuntimeError(
                            f"Validação externa falhou para '{nome}': divergência após gravação."
                        )
                else:
                    raise RuntimeError(
                        f"Validação externa falhou para '{nome}': leitura vazia após gravação."
                    )
            else:
                # Sem loader externo para validar; considera OK se não houve exceção no save
                external_ok = True
        except Exception as e:
            external_ok = False
            external_error = e

    # 2) Sempre salva cópia local (backup/migração)
    path = _XLSX_MAP.get(nome)
    if path:
        _xlsx_save(df, path, sheet_name=nome)

    # 3) Invalida cache da base
    revs = _get_revs()
    revs[nome] = int(revs.get(nome, 0)) + 1

    # 4) Define prioridade de leitura conforme sucesso/fracasso externo
    if external_ok:
        _set_source_override(nome, "external")
    else:
        _set_source_override(nome, "local")

    # 5) Se o externo falhou, informe claramente
    if external_error is not None:
        try:
            st.warning(
                f"[{APP_NAME}] Falha ao salvar no backend do Drive para a base '{nome}'. "
                "Usei a cópia local como fallback (prioridade de leitura local até o próximo sucesso)."
            )
            st.exception(external_error)
        except Exception:
            # Execução fora do Streamlit
            print(f"[WARN] Falha ao salvar no Drive para '{nome}': {external_error}")

# =========================================================
# Utilitários
# =========================================================
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

# =========================================================
# Garantia de Schema (criação/migração mínima)
# =========================================================
def ensure_bases() -> None:
    """Cria/migra as bases mínimas (funciona com Drive via wrapper ou Excel local)."""

    # -------- PROJETOS --------
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

    # -------- ATIVIDADES --------
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

    # -------- FINANCEIRO --------
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

    # -------- PONTOS FOCAIS --------
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

    # -------- RISCOS --------
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
