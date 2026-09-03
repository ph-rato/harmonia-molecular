# -*- coding: utf-8 -*-
import html
import os
import re
from typing import Optional

import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types

# ===========================================================================
# REGRA DO STREAMLIT: st.set_page_config PRECISA SER A PRIMEIRA CHAMADA 'st.'
# ===========================================================================
st.set_page_config(
    page_title="Harmonia Molecular",
    page_icon="🧪",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Constantes de configuração
# ---------------------------------------------------------------------------
FLAVORDB_API_URL: str = "https://flavordb2.com/api/v1/entities"
GEMINI_MODEL: str = "gemini-2.5-flash"
REQUEST_TIMEOUT: int = 20        # segundos por chamada HTTP
MAX_MOLECULES: int = 15          # compostos enviados ao Gemini / exibidos

HTTP_HEADERS: dict = {
    "Accept": "application/json",
    "User-Agent": "HarmoniaMolecular/1.0 (Streamlit MVP)",
}

EXEMPLOS: list = [
    ("🍓 Morango × Manjericão", "strawberry", "basil"),
    ("☕ Café × Maracujá", "coffee", "passion fruit"),
    ("🍫 Chocolate × Laranja", "chocolate", "orange"),
]

CHEF_SYSTEM_PROMPT: str = """Você é o **Chef Tradutor**: especialista em gastronomia molecular, ciência de aromas e design de sabores.
Sua missão é receber dados químicos REAIS do FlavorDB2 e traduzi-los em insights práticos para chefs.

Diretrizes:
1. Responda SEMPRE em português do Brasil.
2. Use Markdown limpo (títulos ##, listas, negrito).
3. Fundamente a análise nos compostos fornecidos.
4. Seja específico e prático: nomeie técnicas, temperaturas e formatos de serviço."""

SETUP_API_KEY_MD: str = """
Obtenha uma chave gratuita no [Google AI Studio](https://aistudio.google.com/apikey) e configure no Streamlit Cloud:
**Settings → Secrets**:

```toml
GEMINI_API_KEY = "SUA_CHAVE_AQUI"
"""

---------------------------------------------------------------------------
Funções Utilitárias e Integrações
---------------------------------------------------------------------------
def obter_gemini_api_key() -> Optional[str]:
"""Obtém a API Key dos secrets do Streamlit ou variáveis de ambiente."""
if "GEMINI_API_KEY" in st.secrets:
return st.secrets["GEMINI_API_KEY"]
if "GOOGLE_API_KEY" in st.secrets:
return st.secrets["GOOGLE_API_KEY"]
return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

@st.cache_data(ttl=3600)
def buscar_dados_flavordb(ingrediente: str) -> Optional[dict]:
"""Consulta a API do FlavorDB2 para resgatar perfil e moléculas."""
try:
url = f"{FLAVORDB_API_URL}?name={ingrediente.strip().lower()}"
response = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
response.raise_for_status()
data = response.json()

    if not data or "entities" not in data or not data["entities"]:
        return None
        
    entidade = data["entities"][0]
    moleculas = [c["name"] for c in entidade.get("molecules", [])]
    perfil = entidade.get("flavor_profile", [])
    
    return {
        "nome": ingrediente,
        "moleculas": moleculas[:MAX_MOLECULES],
        "perfil": perfil
    }
except Exception as e:
    st.error(f"Erro ao consultar FlavorDB2 para '{ingrediente}': {e}")
    return None
def analisar_harmonizacao(d_ing1: dict, d_ing2: dict, api_key: str) -> str:
"""Aciona a API do Gemini com o papel de Chef Tradutor."""
client = genai.Client(api_key=api_key)

set1, set2 = set(d_ing1["moleculas"]), set(d_ing2["moleculas"])
em_comum = list(set1.intersection(set2))

user_prompt = f"""
Analise a harmonização molecular entre os dois ingredientes abaixo:

--- INGREDIENTE 1: {d_ing1['nome'].upper()} ---
- Perfil Sensorial: {', '.join(d_ing1['perfil']) if d_ing1['perfil'] else 'Não informado'}
- Principais Compostos: {', '.join(d_ing1['moleculas'])}

--- INGREDIENTE 2: {d_ing2['nome'].upper()} ---
- Perfil Sensorial: {', '.join(d_ing2['perfil']) if d_ing2['perfil'] else 'Não informado'}
- Principais Compostos: {', '.join(d_ing2['moleculas'])}

--- DADOS DE INTERSECÇÃO ---
- Moléculas Compartilhadas Encontradas: {', '.join(em_comum) if em_comum else 'Nenhuma molécula idêntica direta nas principais listadas'}

Forneça uma análise gastronômica completa estruturada da seguinte forma:
## 1. Sinergia Molecular e Perfil Aromático
## 2. Equilíbrio de Sabores (Gostos Básicos, Gordura e Acidez)
## 3. Aplicação Prática & Sugestão de Prato
"""

response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=user_prompt,
    config=types.GenerateContentConfig(
        system_instruction=CHEF_SYSTEM_PROMPT,
        temperature=0.3,
    )
)
return response.text
---------------------------------------------------------------------------
Interface Gráfica
---------------------------------------------------------------------------
st.title("🧪 Harmonia Molecular")
st.caption("Gastronomia Molecular orientada por IA e Dados Biológicos Reais")

api_key = obter_gemini_api_key()
if not api_key:
st.warning("⚠️ API Key do Gemini não foi configurada.")
st.markdown(SETUP_API_KEY_MD)
st.stop()

st.subheader("Selecione os Ingredientes")
col_ex1, col_ex2, col_ex3 = st.columns(3)

ing1_default, ing2_default = "coffee", "passion fruit"

if col_ex1.button(EXEMPLOS[0][0]):
ing1_default, ing2_default = EXEMPLOS[0][1], EXEMPLOS[0][2]
if col_ex2.button(EXEMPLOS[1][0]):
ing1_default, ing2_default = EXEMPLOS[1][1], EXEMPLOS[1][2]
if col_ex3.button(EXEMPLOS[2][0]):
ing1_default, ing2_default = EXEMPLOS[2][1], EXEMPLOS[2][2]

col1, col2 = st.columns(2)
with col1:
ing1 = st.text_input("Ingrediente Base (em inglês):", value=ing1_default)
with col2:
ing2 = st.text_input("Ingrediente Alvo (em inglês):", value=ing2_default)

if st.button("Analisar Harmonização Molecular", type="primary"):
if not ing1 or not ing2:
st.error("Por favor, preencha os dois ingredientes.")
else:
with st.spinner("Consultando dados biológicos no FlavorDB2 e processando no Gemini..."):
dados1 = buscar_dados_flavordb(ing1)
dados2 = buscar_dados_flavordb(ing2)

        if not dados1:
            st.error(f"Ingrediente '{ing1}' não foi encontrado no FlavorDB2.")
        elif not dados2:
            st.error(f"Ingrediente '{ing2}' não foi encontrado no FlavorDB2.")
        else:
            st.success("Dados do FlavorDB2 extraídos com sucesso!")
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.markdown(f"### {ing1.title()}")
                st.write("**Perfil:**", ", ".join(dados1["perfil"]))
                st.write("**Moléculas:**", ", ".join(dados1["moleculas"]))
            with col_d2:
                st.markdown(f"### {ing2.title()}")
                st.write("**Perfil:**", ", ".join(dados2["perfil"]))
                st.write("**Moléculas:**", ", ".join(dados2["moleculas"]))
            
            st.divider()
            
            resultado_ia = analisar_harmonizacao(dados1, dados2, api_key)
            st.markdown(resultado_ia)
