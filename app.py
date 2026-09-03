# -*- coding: utf-8 -*-
"""
Harmonia Molecular — Gastronomia Molecular com IA (MVP de custo $0)
====================================================================

Aplicação web que:
  1. Consulta compostos aromáticos REAIS de ingredientes na API REST do
     FlavorDB2 (https://flavordb2.com/api/v1/entities?name={ingrediente});
  2. Cruza a afinidade molecular entre dois ingredientes (moléculas
     aromáticas compartilhadas + índice de Jaccard);
  3. Aciona o Google Gemini (gemini-2.5-flash) como "Chef Tradutor" para
     converter a química em análise sensorial, técnica e prato pronto.

Arquitetura 100% online & cloud:
  - Interface ........ Streamlit (pronta para o Community Cloud)
  - Dados químicos ... FlavorDB2 REST API
  - IA ............... SDK oficial `google-genai`

Segurança da API Key (nunca hardcoded):
  - Local ............ .streamlit/secrets.toml   ->  GEMINI_API_KEY = "..."
  - Community Cloud ... Settings → Secrets      ->  GEMINI_API_KEY = "..."
  - Fallback .......... variáveis de ambiente GEMINI_API_KEY / GOOGLE_API_KEY

Execução local:
  $ pip install -r requirements.txt
  $ streamlit run app.py
"""

import html
import os
import re
from typing import Optional

import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types

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

CHEF_SYSTEM_PROMPT: str = """Você é o **Chef Tradutor**: especialista em gastronomia molecular, ciência \
de aromas e design de sabores, com passagem por cozinhas de alto padrão e laboratórios de flavor.

Sua missão é receber dados químicos REAIS — compostos aromáticos voláteis extraídos do banco \
FlavorDB2 — e traduzi-los em insights práticos para chefs, food designers e entusiastas da \
ciência do sabor.

Diretrizes:
1. Responda SEMPRE em português do Brasil.
2. Use Markdown limpo (títulos ##, listas, negrito) — o texto será exibido em uma interface web.
3. Fundamente a análise nos compostos fornecidos; quando for além deles, use linguagem \
probabilística ("tende a", "provavelmente").
4. Seja específico e prático: nomeie técnicas, temperaturas e formatos de serviço. Evite \
generalidades.
5. Jamais invente moléculas que não constem nos dados fornecidos.
6. Se a combinação for desafiadora, proponha caminhos de equilíbrio em vez de descartá-la."""

SETUP_API_KEY_MD: str = ""
Obtenha uma chave gratuita no **[Google AI Studio](https://aistudio.google.com/apikey)** e:

**Execução local** — crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:

```toml
GEMINI_API_KEY = "SUA_CHAVE_AQUI"
