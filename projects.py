# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st

# utilidades e garantia de bases
try:
    from common import APP_NAME, ensure_bases
except ModuleNotFoundError:
    APP_NAME = "Gestão de Projetos"
    def ensure_bases():  # fallback no caso de você ainda não ter o common.py
        pass

# Importa cada aba do módulo correspondente
from abas.projetos_escopo import aba_projetos_escopo
from abas.cadastro_atividades import aba_cadastro_atividades
from abas.agenda import aba_agenda
from abas.financeiro import aba_financeiro
from abas.pontos_focais import aba_pontos_focais
from abas.riscos import aba_riscos
from abas.visao_unificada import aba_visao_unificada

st.set_page_config(page_title=APP_NAME, page_icon="📁", layout="wide")

def sidebar_menu() -> str:
    st.sidebar.title(APP_NAME)
    st.sidebar.caption("Projetos integrados: escopo, atividades, agenda, financeiro, pontos focais e riscos")
    pagina = st.sidebar.radio(
        "Navegação",
        (
            "📁 Projetos & Escopo",
            "✅ Cadastro de Atividades",
            "🗓️ Agenda",
            "💰 Financeiro do Projeto",
            "👥 Pontos Focais",
            "⚠️ Riscos do Projeto",
            "📊 Visão Unificada",
        ),
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        "**Dica:** a *Visão Unificada* consolida tudo por projeto.\n\n"
        "Defina o diretório de dados com a variável de ambiente `APP_DATA_DIR`."
    )
    return pagina

def main() -> None:
    # garante que os CSVs/planilhas mínimas existam (implementado em common.py)
    ensure_bases()

    pagina = sidebar_menu()

    if pagina == "📁 Projetos & Escopo":
        aba_projetos_escopo(st)
    elif pagina == "✅ Cadastro de Atividades":
        aba_cadastro_atividades(st)
    elif pagina == "🗓️ Agenda":
        aba_agenda(st)
    elif pagina == "💰 Financeiro do Projeto":
        aba_financeiro(st)
    elif pagina == "👥 Pontos Focais":
        aba_pontos_focais(st)
    elif pagina == "⚠️ Riscos do Projeto":
        aba_riscos(st)
    elif pagina == "📊 Visão Unificada":
        aba_visao_unificada(st)

if __name__ == "__main__":
    main()
