# -*- coding: utf-8 -*-

import os
from typing import Optional, Dict, Any, List, Set

import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

st.set_page_config(
    page_title="Harmonia Molecular",
    page_icon="🧪",
    layout="wide",
)

FLAVORDB_API_URL = "https://flavordb2.com/api/v1/entities"
GEMINI_MODEL = "gemini-2.5-flash"

REQUEST_TIMEOUT = 20
MAX_MOLECULES = 15

HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "HarmoniaMolecular/1.0",
}

EXEMPLOS = [
    ("🍓 Morango × Manjericão", "strawberry", "basil"),
    ("☕ Café × Maracujá", "coffee", "passion fruit"),
    ("🍫 Chocolate × Laranja", "chocolate", "orange"),
]

CHEF_SYSTEM_PROMPT = """
Você é o Chef Tradutor: especialista em gastronomia, ciência de aromas,
harmonização de sabores e desenvolvimento de pratos.

Sua missão é receber dados de compostos aromáticos e traduzi-los em uma
análise gastronômica prática.

REGRAS:

1. Responda sempre em português do Brasil.
2. Use Markdown limpo.
3. Fundamente a análise nos compostos fornecidos.
4. Não invente moléculas que não estejam nos dados.
5. Diferencie claramente dados químicos de interpretações gastronômicas.
6. Considere aroma, sabor, acidez, doçura, amargor, gordura, textura e
   temperatura.
7. Seja específico nas sugestões culinárias.
8. Ao sugerir um prato, indique técnicas culinárias, temperatura aproximada,
   textura e formato de serviço.
9. Moléculas compartilhadas sugerem uma possível ponte aromática, mas não
   garantem, sozinhas, que dois ingredientes sejam agradáveis juntos.
"""


# ============================================================================
# GEMINI
# ============================================================================

def obter_gemini_api_key() -> Optional[str]:
    """Obtém a API Key do Gemini a partir dos Secrets ou variáveis de ambiente."""

    try:
        if "GEMINI_API_KEY" in st.secrets:
            chave = str(st.secrets["GEMINI_API_KEY"]).strip()

            if chave:
                return chave

        if "GOOGLE_API_KEY" in st.secrets:
            chave = str(st.secrets["GOOGLE_API_KEY"]).strip()

            if chave:
                return chave

    except Exception:
        pass

    chave = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )

    return chave.strip() if chave else None


# ============================================================================
# FLAVORDB
# ============================================================================

def extrair_entidades(data: Any) -> List[Dict[str, Any]]:
    """
    Normaliza diferentes formatos possíveis de resposta da API do FlavorDB.
    """

    if isinstance(data, list):
        return [
            item
            for item in data
            if isinstance(item, dict)
        ]

    if not isinstance(data, dict):
        return []

    for chave in ("entities", "data", "results"):

        valor = data.get(chave)

        if isinstance(valor, list):
            return [
                item
                for item in valor
                if isinstance(item, dict)
            ]

        if isinstance(valor, dict):
            return [valor]

    if any(
        chave in data
        for chave in (
            "molecules",
            "flavor_compounds",
            "compounds",
            "flavor_profile",
        )
    ):
        return [data]

    return []


def extrair_nome_composto(composto: Any) -> Optional[str]:
    """Tenta encontrar o nome de um composto."""

    if isinstance(composto, str):
        nome = composto.strip()
        return nome if nome else None

    if not isinstance(composto, dict):
        return None

    for chave in (
        "name",
        "common_name",
        "molecule_name",
        "compound_name",
    ):

        valor = composto.get(chave)

        if valor:
            nome = str(valor).strip()

            if nome:
                return nome

    return None


def extrair_moleculas(entidade: Dict[str, Any]) -> Set[str]:
    """Extrai moléculas ou compostos aromáticos de uma entidade."""

    moleculas: Set[str] = set()

    possiveis_chaves = (
        "molecules",
        "flavor_compounds",
        "compounds",
        "flavors",
    )

    for chave in possiveis_chaves:

        compostos = entidade.get(chave, [])

        if isinstance(compostos, dict):
            compostos = [compostos]

        if isinstance(compostos, str):
            compostos = [compostos]

        if not isinstance(compostos, list):
            continue

        for composto in compostos:

            nome = extrair_nome_composto(composto)

            if nome:
                moleculas.add(nome)

    return moleculas


def extrair_perfil(entidade: Dict[str, Any]) -> List[str]:
    """Extrai o perfil sensorial/aromático."""

    possiveis_chaves = (
        "flavor_profile",
        "flavor_profile_names",
        "flavors",
        "profile",
    )

    for chave in possiveis_chaves:

        perfil = entidade.get(chave)

        if not perfil:
            continue

        if isinstance(perfil, str):
            return [perfil.strip()]

        if isinstance(perfil, dict):
            perfil = [perfil]

        if isinstance(perfil, list):

            resultado = []

            for item in perfil:

                if isinstance(item, str):

                    nome = item.strip()

                    if nome:
                        resultado.append(nome)

                elif isinstance(item, dict):

                    nome = (
                        item.get("name")
                        or item.get("flavor")
                        or item.get("label")
                    )

                    if nome:
                        resultado.append(str(nome).strip())

            return resultado

    return []


@st.cache_data(ttl=3600)
def buscar_dados_flavordb(
    ingrediente: str,
) -> Optional[Dict[str, Any]]:
    """
    Consulta o FlavorDB2 e retorna dados normalizados.
    """

    ingrediente_limpo = ingrediente.strip().lower()

    if not ingrediente_limpo:
        return None

    try:

        response = requests.get(
            FLAVORDB_API_URL,
            params={"name": ingrediente_limpo},
            headers=HTTP_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

    except requests.Timeout:

        st.error(
            f"O FlavorDB demorou demais para responder para "
            f"'{ingrediente}'."
        )

        return None

    except requests.HTTPError as exc:

        status_code = (
            exc.response.status_code
            if exc.response is not None
            else "desconhecido"
        )

        st.error(
            f"O FlavorDB retornou um erro HTTP "
            f"({status_code}) para '{ingrediente}'."
        )

        return None

    except requests.RequestException as exc:

        st.error(
            f"Erro de conexão com o FlavorDB para "
            f"'{ingrediente}': {exc}"
        )

        return None

    except ValueError:

        st.error(
            f"O FlavorDB retornou uma resposta que não é JSON "
            f"para '{ingrediente}'."
        )

        return None

    except Exception as exc:

        st.error(
            f"Erro inesperado ao consultar o FlavorDB "
            f"para '{ingrediente}': {exc}"
        )

        return None

    entidades = extrair_entidades(data)

    if not entidades:
        return None

    # Procura primeiro uma entidade que realmente contenha compostos.
    entidade_escolhida = None

    for entidade in entidades:

        moleculas = extrair_moleculas(entidade)

        if moleculas:
            entidade_escolhida = entidade
            break

    if entidade_escolhida is None:
        entidade_escolhida = entidades[0]

    moleculas = extrair_moleculas(entidade_escolhida)
    perfil = extrair_perfil(entidade_escolhida)

    return {
        "nome": ingrediente.strip(),
        "moleculas": sorted(moleculas)[:MAX_MOLECULES],
        "perfil": perfil,
    }


# ============================================================================
# ANÁLISE MOLECULAR
# ============================================================================

def calcular_jaccard(
    moleculas_a: Set[str],
    moleculas_b: Set[str],
) -> float:
    """Calcula o índice de Jaccard entre dois conjuntos."""

    uniao = moleculas_a | moleculas_b

    if not uniao:
        return 0.0

    interseccao = moleculas_a & moleculas_b

    return len(interseccao) / len(uniao)


def analisar_harmonizacao(
    dados_ing1: Dict[str, Any],
    dados_ing2: Dict[str, Any],
    api_key: str,
) -> str:
    """Envia os dados moleculares para o Gemini."""

    moleculas_1 = set(
        dados_ing1.get("moleculas", [])
    )

    moleculas_2 = set(
        dados_ing2.get("moleculas", [])
    )

    em_comum = sorted(
        moleculas_1 & moleculas_2
    )

    jaccard = calcular_jaccard(
        moleculas_1,
        moleculas_2,
    )

    perfil_1 = dados_ing1.get("perfil", [])
    perfil_2 = dados_ing2.get("perfil", [])

    perfil_1_texto = (
        ", ".join(perfil_1)
        if perfil_1
        else "Não informado"
    )

    perfil_2_texto = (
        ", ".join(perfil_2)
        if perfil_2
        else "Não informado"
    )

    moleculas_1_texto = (
        ", ".join(sorted(moleculas_1))
        if moleculas_1
        else "Nenhuma encontrada"
    )

    moleculas_2_texto = (
        ", ".join(sorted(moleculas_2))
        if moleculas_2
        else "Nenhuma encontrada"
    )

    compartilhadas_texto = (
        ", ".join(em_comum)
        if em_comum
        else "Nenhuma molécula idêntica encontrada"
    )

    user_prompt = f"""
Analise a harmonização molecular entre os dois ingredientes abaixo.

==============================
INGREDIENTE 1
==============================

Nome:
{dados_ing1["nome"]}

Perfil sensorial/aromático:
{perfil_1_texto}

Principais compostos encontrados:
{moleculas_1_texto}


==============================
INGREDIENTE 2
==============================

Nome:
{dados_ing2["nome"]}

Perfil sensorial/aromático:
{perfil_2_texto}

Principais compostos encontrados:
{moleculas_2_texto}


==============================
INTERSECÇÃO MOLECULAR
==============================

Moléculas compartilhadas:
{compartilhadas_texto}

Índice de Jaccard:
{jaccard:.2f}


==============================
TAREFA
==============================

Produza uma análise gastronômica estruturada nos seguintes tópicos:

## 1. Sinergia Molecular e Perfil Aromático

Explique quais compostos podem funcionar como pontes aromáticas entre os
ingredientes.

Se houver moléculas compartilhadas, explique sua possível contribuição.

Se não houver moléculas compartilhadas, explique por que a combinação ainda
pode funcionar através de complementaridade sensorial.

Não invente compostos.

## 2. Equilíbrio de Sabores

Analise:

- doçura
- acidez
- amargor
- umami
- salinidade
- gordura
- intensidade aromática
- persistência

Explique possíveis desequilíbrios e como corrigi-los.

## 3. Aplicação Técnica

Explique quais técnicas culinárias podem favorecer a combinação.

Considere, quando fizer sentido:

- cocção
- caramelização
- torra
- fermentação
- infusão
- emulsão
- redução
- extração
- temperatura de serviço
- textura

## 4. Prato Proposto

Crie uma proposta de prato utilizando os dois ingredientes.

Informe:

- nome criativo
- conceito
- principais componentes
- técnica de preparo
- temperatura de serviço
- textura
- montagem
- formato de serviço

## 5. Conclusão

Classifique a combinação como:

- muito promissora
- promissora
- interessante
- desafiadora

Explique brevemente o motivo.

IMPORTANTE:

O índice de Jaccard é apenas um indicador de similaridade entre os conjuntos
de compostos fornecidos. Ele não representa, sozinho, a qualidade
gastronômica da combinação.

Não trate o índice de Jaccard como uma probabilidade de compatibilidade.

Não invente dados químicos que não foram fornecidos.
"""

    try:

        client = genai.Client(
            api_key=api_key,
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=CHEF_SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )

        texto = getattr(response, "text", None)

        if texto:
            return texto.strip()

        return (
            "O Gemini recebeu a solicitação, "
            "mas não retornou texto."
        )

    except Exception as exc:

        return (
            "### Erro ao consultar o Gemini\n\n"
            f"`{exc}`\n\n"
            "Verifique se a API Key está correta e se o modelo "
            f"`{GEMINI_MODEL}` está disponível para sua chave."
        )


# ============================================================================
# INTERFACE
# ============================================================================

st.title("🧪 Harmonia Molecular")

st.caption(
    "Gastronomia Molecular orientada por IA e dados de compostos aromáticos."
)


# ============================================================================
# API KEY
# ============================================================================

api_key = obter_gemini_api_key()

if not api_key:

    st.warning(
        "A API Key do Gemini não foi configurada."
    )

    st.markdown(
        """
### Configure sua API Key do Gemini

No Streamlit Cloud, vá em:

**Settings → Secrets**

Adicione:

```toml
GEMINI_API_KEY = "SUA_CHAVE_AQUI"
