# -*- coding: utf-8 -*-
import streamlit as st

# Importa abas
from abas.projetos_escopo import aba_projetos_escopo
from abas.cadastro_atividades import aba_cadastro_atividades
from abas.agenda import aba_agenda
from abas.financeiro import aba_financeiro
from abas.pontos_focais import aba_pontos_focais
from abas.riscos import aba_riscos
from abas.visao_unificada import aba_visao_unificada

# para badge e invalidação seletiva
import sys
from common import load_base, save_base  # só para garantir import e warming
try:
    import app_storage  # type: ignore
    HAVE_APP_STORAGE = True
except Exception:
    HAVE_APP_STORAGE = False

st.set_page_config(page_title="Gestão de Projetos", layout="wide")

def _storage_badge() -> str:
    # heurística simples: se app_storage carregou e conectar_drive existe, assume Drive
    if HAVE_APP_STORAGE and hasattr(app_storage, "conectar_drive"):
        return "Drive"
    return "Excel local"

def _invalidate_all():
    # Limpa apenas caches de dados. Isso evita recomputar UI desnecessariamente.
    # Se sua versão do Streamlit suportar, isso limpa o cache de @st.cache_data.
    try:
        st.cache_data.clear()
    except Exception:
        pass
    # Incrementa os "revs" para forçar recarregar bases no próximo load_base
    st.session_state.setdefault("_data_revs", {})
    for nome in ["projetos", "atividades", "financeiro", "pontos_focais", "riscos"]:
        st.session_state["_data_revs"][nome] = int(st.session_state["_data_revs"].get(nome, 0)) + 1

def sidebar():
    st.sidebar.title("Gestão de Projetos")
    st.sidebar.caption("Projetos integrados: escopo, atividades, agenda,\nfinanceiro, pontos focais e riscos")

    # Badge de onde está salvando os dados
    st.sidebar.markdown(
        f"<div style='padding:6px 10px;border-radius:8px;background:#eef3ff;border:1px solid #cad7ff;width:max-content'>"
        f"<strong>Armazenamento:</strong> {_storage_badge()}</div>",
        unsafe_allow_html=True,
    )

    # Botão de atualizar dados (limpa cache só quando você quer)
    if st.sidebar.button("🔄 Atualizar dados"):
        _invalidate_all()
        st.sidebar.success("Dados recarregados.")

    st.sidebar.write("—")
    st.sidebar.caption("Dica: a **Visão Unificada** consolida tudo por projeto.\n"
                       "Defina o diretório de dados com a variável de ambiente `APP_DATA_DIR`.")

    menu = st.sidebar.radio(
        "Navegação",
        [
            "📁 Projetos & Escopo",
            "✅ Cadastro de Atividades",
            "🗓️ Agenda",
            "💰 Financeiro do Projeto",
            "👥 Pontos Focais",
            "⚠️ Riscos do Projeto",
            "📊 Visão Unificada",
        ],
        index=0,
        key="menu_sel",
    )
    return menu

def run():
    menu = sidebar()

    # Importante: todo input que puder, coloque em st.form dentro das abas
    if menu == "📁 Projetos & Escopo":
        aba_projetos_escopo(st)
    elif menu == "✅ Cadastro de Atividades":
        aba_cadastro_atividades(st)
    elif menu == "🗓️ Agenda":
        aba_agenda(st)
    elif menu == "💰 Financeiro do Projeto":
        aba_financeiro(st)
    elif menu == "👥 Pontos Focais":
        aba_pontos_focais(st)
    elif menu == "⚠️ Riscos do Projeto":
        aba_riscos(st)
    elif menu == "📊 Visão Unificada":
        aba_visao_unificada(st)

if __name__ == "__main__":
    run()
