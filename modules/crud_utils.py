import pandas as pd
import streamlit as st
import tempfile
from modules.drive_utils import conectar_drive
import openpyxl

def carregar_arquivo_excel(nome_arquivo):
    drive = conectar_drive()
    arquivos = drive.ListFile({'q': f"title = '{nome_arquivo}' and trashed=false"}).GetList()

    if not arquivos:
        return pd.DataFrame()

    caminho_temp = tempfile.NamedTemporaryFile(delete=False).name
    arquivos[0].GetContentFile(caminho_temp)

    try:
        return pd.read_excel(caminho_temp)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {nome_arquivo}: {e}")
        return pd.DataFrame()

def salvar_arquivo_excel(df, nome_arquivo):
    drive = conectar_drive()
    caminho_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx").name
    df.to_excel(caminho_temp, index=False)

    arquivos = drive.ListFile({'q': f"title = '{nome_arquivo}' and trashed=false"}).GetList()
    if arquivos:
        arquivo = arquivos[0]
    else:
        arquivo = drive.CreateFile({'title': nome_arquivo})

    arquivo.SetContentFile(caminho_temp)
    arquivo.Upload()

