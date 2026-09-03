````python
# -*- coding: utf-8 -*-

import os
from typing import Optional, Dict, Any, List, Set, Tuple

import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types


# ============================================================================
# CONFIGURAÇÃO DO STREAMLIT
# ============================================================================

st.set_page_config(
    page_title="Harmonia Molecular",
    page_icon="🧪",
    layout="wide",
)


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

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
9. Lembre que moléculas compartilhadas sugerem uma possível ponte aromática,
   mas não garantem, sozinhas, que dois ingredientes sejam agradáveis juntos.
"""


SETUP_API_KEY_MD = """
### 🔑 Configure sua API Key do Gemini

Você pode obter uma chave no Google AI Studio.

No **Streamlit Cloud**, vá em:

**Settings → Secrets**

e adicione:

```toml
GEMINI_API_KEY = "SUA_CHAVE_AQUI"
````

Depois salve e reinicie o aplicativo.
"""

# ============================================================================

# GEMINI

# ============================================================================

def obter_gemini_api_key() -> Optional[str]:
"""
Obtém a API Key do Gemini.

```
Primeiro procura nos Secrets do Streamlit.
Depois procura nas variáveis de ambiente.
"""

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
    # Fora do Streamlit ou quando secrets.toml não existe.
    pass

return (
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
)
```

# ============================================================================

# FLAVORDB

# ============================================================================

def extrair_entidades(data: Any) -> List[Dict[str, Any]]:
"""
Normaliza diferentes formatos possíveis de resposta da API.
"""

```
if isinstance(data, list):
    return [
        item
        for item in data
        if isinstance(item, dict)
    ]

if not isinstance(data, dict):
    return []

# Formatos possíveis.
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

# Caso a própria resposta seja uma entidade.
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
```

def extrair_nome_composto(composto: Any) -> Optional[str]:
"""
Tenta encontrar o nome de um composto em diferentes formatos.
"""

```
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
        return str(valor).strip()

return None
```

def extrair_moleculas(entidade: Dict[str, Any]) -> Set[str]:
"""
Extrai moléculas/compostos aromáticos de uma entidade.
"""

```
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

    if not isinstance(compostos, list):
        continue

    for composto in compostos:

        nome = extrair_nome_composto(composto)

        if nome:
            moleculas.add(nome)

return moleculas
```

def extrair_perfil(entidade: Dict[str, Any]) -> List[str]:
"""
Extrai o perfil sensorial/aromático.
"""

```
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
        return [perfil]

    if isinstance(perfil, list):

        resultado = []

        for item in perfil:

            if isinstance(item, str):
                resultado.append(item)

            elif isinstance(item, dict):

                nome = (
                    item.get("name")
                    or item.get("flavor")
                    or item.get("label")
                )

                if nome:
                    resultado.append(str(nome))

        return resultado

return []
```

@st.cache_data(ttl=3600)
def buscar_dados_flavordb(
ingrediente: str,
) -> Optional[Dict[str, Any]]:
"""
Consulta o FlavorDB2 e retorna dados normalizados.
"""

```
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

except requests.RequestException as exc:

    st.error(
        f"Erro de conexão com o FlavorDB2 para "
        f"'{ingrediente}': {exc}"
    )

    return None

except ValueError:

    st.error(
        f"O FlavorDB2 retornou uma resposta que não é JSON "
        f"para '{ingrediente}'."
    )

    return None

except Exception as exc:

    st.error(
        f"Erro inesperado ao consultar o FlavorDB2 "
        f"para '{ingrediente}': {exc}"
    )

    return None

entidades = extrair_entidades(data)

if not entidades:
    return None

# Procuramos a primeira entidade que contenha moléculas.
entidade_escolhida = None

for entidade in entidades:

    moleculas = extrair_moleculas(entidade)

    if moleculas:
        entidade_escolhida = entidade
        break

# Se nenhuma tiver moléculas, usamos a primeira para permitir
# diagnóstico do perfil.
if entidade_escolhida is None:
    entidade_escolhida = entidades[0]

moleculas = extrair_moleculas(entidade_escolhida)

perfil = extrair_perfil(entidade_escolhida)

return {
    "nome": ingrediente.strip(),
    "moleculas": sorted(moleculas)[:MAX_MOLECULES],
    "perfil": perfil,
}
```

# ============================================================================

# ANÁLISE MOLECULAR

# ============================================================================

def calcular_jaccard(
moleculas_a: Set[str],
moleculas_b: Set[str],
) -> float:
"""
Calcula o índice de Jaccard entre dois conjuntos.
"""

```
uniao = moleculas_a | moleculas_b

if not uniao:
    return 0.0

interseccao = moleculas_a & moleculas_b

return len(interseccao) / len(uniao)
```

def analisar_harmonizacao(
dados_ing1: Dict[str, Any],
dados_ing2: Dict[str, Any],
api_key: str,
) -> str:
"""
Envia os dados moleculares para o Gemini e solicita
uma interpretação gastronômica.
"""

```
moleculas_1 = set(dados_ing1.get("moleculas", []))
moleculas_2 = set(dados_ing2.get("moleculas", []))

em_comum = sorted(moleculas_1 & moleculas_2)

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
```

Analise a harmonização molecular entre os dois ingredientes abaixo.

==============================
INGREDIENTE 1
=============

Nome:
{dados_ing1["nome"]}

Perfil sensorial/aromático:
{perfil_1_texto}

Principais compostos encontrados:
{moleculas_1_texto}

==============================
INGREDIENTE 2
=============

Nome:
{dados_ing2["nome"]}

Perfil sensorial/aromático:
{perfil_2_texto}

Principais compostos encontrados:
{moleculas_2_texto}

==============================
INTERSECÇÃO MOLECULAR
=====================

Moléculas compartilhadas:
{compartilhadas_texto}

Índice de Jaccard:
{jaccard:.2f}

==============================
TAREFA
======

Produza uma análise gastronômica estruturada exatamente nos seguintes
tópicos:

## 1. 🧬 Sinergia Molecular e Perfil Aromático

Explique quais compostos podem funcionar como pontes aromáticas entre os
ingredientes.

Se houver moléculas compartilhadas, explique sua possível contribuição.

Se não houver moléculas compartilhadas, explique por que a combinação ainda
pode funcionar através de complementaridade sensorial.

Não invente compostos.

## 2. 👅 Equilíbrio de Sabores

Analise:

* doçura
* acidez
* amargor
* umami
* salinidade
* gordura
* intensidade aromática
* persistência

Explique possíveis desequilíbrios e como corrigi-los.

## 3. 👨‍🍳 Aplicação Técnica

Explique quais técnicas culinárias podem favorecer a combinação.

Considere, quando fizer sentido:

* cocção
* caramelização
* torra
* fermentação
* infusão
* emulsão
* redução
* extração
* temperatura de serviço
* textura

## 4. 🍽️ Prato Proposto

Crie uma proposta de prato utilizando os dois ingredientes.

Informe:

* nome criativo
* conceito
* principais componentes
* técnica de preparo
* temperatura de serviço
* textura
* montagem
* formato de serviço

## 5. 💡 Conclusão

Diga se considera a combinação:

**muito promissora, promissora, interessante ou desafiadora**

e explique brevemente o motivo.

IMPORTANTE:
O índice de Jaccard é apenas um indicador de similaridade entre os
conjuntos de compostos fornecidos. Ele não representa, sozinho, a qualidade
gastronômica da combinação.
"""

```
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
        return texto

    return (
        "⚠️ O Gemini recebeu a solicitação, "
        "mas não retornou texto."
    )

except Exception as exc:

    return (
        "⚠️ **Erro ao consultar o Gemini.**\n\n"
        f"`{exc}`\n\n"
        "Verifique se a API Key está correta e se o modelo "
        f"`{GEMINI_MODEL}` está disponível para sua chave."
    )
```

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

```
st.warning(
    "⚠️ A API Key do Gemini não foi configurada."
)

st.markdown(SETUP_API_KEY_MD)

st.stop()
```

# ============================================================================

# SELEÇÃO DE INGREDIENTES

# ============================================================================

st.subheader("🥘 Escolha os ingredientes")

# Inicialização do estado.

if "ingrediente_1" not in st.session_state:
st.session_state.ingrediente_1 = "coffee"

if "ingrediente_2" not in st.session_state:
st.session_state.ingrediente_2 = "passion fruit"

col_ex1, col_ex2, col_ex3 = st.columns(3)

if col_ex1.button(
EXEMPLOS[0][0],
use_container_width=True,
):
st.session_state.ingrediente_1 = EXEMPLOS[0][1]
st.session_state.ingrediente_2 = EXEMPLOS[0][2]

if col_ex2.button(
EXEMPLOS[1][0],
use_container_width=True,
):
st.session_state.ingrediente_1 = EXEMPLOS[1][1]
st.session_state.ingrediente_2 = EXEMPLOS[1][2]

if col_ex3.button(
EXEMPLOS[2][0],
use_container_width=True,
):
st.session_state.ingrediente_1 = EXEMPLOS[2][1]
st.session_state.ingrediente_2 = EXEMPLOS[2][2]

# ============================================================================

# CAMPOS

# ============================================================================

col1, col2 = st.columns(2)

with col1:

```
ing1 = st.text_input(
    "Ingrediente Base (em inglês)",
    key="ingrediente_1",
    placeholder="Ex.: strawberry",
)
```

with col2:

```
ing2 = st.text_input(
    "Ingrediente Alvo (em inglês)",
    key="ingrediente_2",
    placeholder="Ex.: basil",
)
```

# ============================================================================

# BOTÃO DE ANÁLISE

# ============================================================================

if st.button(
"🔎 Analisar Harmonização Molecular",
type="primary",
use_container_width=True,
):

```
ing1 = ing1.strip()
ing2 = ing2.strip()

if not ing1 or not ing2:

    st.error(
        "Por favor, preencha os dois ingredientes."
    )

    st.stop()


# ------------------------------------------------------------------------
# BUSCA FLAVORDB
# ------------------------------------------------------------------------

with st.spinner(
    "🧪 Consultando os compostos aromáticos..."
):

    dados1 = buscar_dados_flavordb(ing1)
    dados2 = buscar_dados_flavordb(ing2)


if not dados1:

    st.error(
        f"Não encontrei dados para **{ing1}** no FlavorDB."
    )

    st.info(
        "Tente utilizar o nome do ingrediente em inglês. "
        "Ex.: `strawberry`, `coffee`, `orange`."
    )

    st.stop()


if not dados2:

    st.error(
        f"Não encontrei dados para **{ing2}** no FlavorDB."
    )

    st.info(
        "Tente utilizar o nome do ingrediente em inglês."
    )

    st.stop()


# ------------------------------------------------------------------------
# DADOS MOLECULARES
# ------------------------------------------------------------------------

moleculas1 = set(dados1.get("moleculas", []))
moleculas2 = set(dados2.get("moleculas", []))

compartilhadas = sorted(
    moleculas1 & moleculas2
)

jaccard = calcular_jaccard(
    moleculas1,
    moleculas2,
)


st.success(
    "✅ Dados dos ingredientes carregados."
)


# ------------------------------------------------------------------------
# RESUMO
# ------------------------------------------------------------------------

st.subheader("📊 Resultado da análise")


m1, m2, m3 = st.columns(3)


m1.metric(
    f"Compostos · {ing1.title()}",
    len(moleculas1),
)


m2.metric(
    f"Compostos · {ing2.title()}",
    len(moleculas2),
)


m3.metric(
    "Moléculas em comum",
    len(compartilhadas),
)


st.progress(
    min(max(jaccard, 0.0), 1.0),
    text=f"Índice de Jaccard: {jaccard:.2f}",
)


# ------------------------------------------------------------------------
# PERFIS
# ------------------------------------------------------------------------

col_d1, col_d2 = st.columns(2)


with col_d1:

    st.markdown(
        f"### 🧪 {ing1.title()}"
    )

    perfil1 = dados1.get("perfil", [])

    if perfil1:
        st.write(
            "**Perfil aromático:**",
            ", ".join(perfil1),
        )
    else:
        st.write(
            "**Perfil aromático:** Não informado"
        )

    if moleculas1:

        st.write(
            "**Principais compostos:**"
        )

        st.dataframe(
            pd.DataFrame(
                sorted(moleculas1),
                columns=["Composto aromático"],
            ),
            hide_index=True,
            use_container_width=True,
        )

    else:

        st.info(
            "Nenhum composto aromático encontrado."
        )


with col_d2:

    st.markdown(
        f"### 🧪 {ing2.title()}"
    )

    perfil2 = dados2.get("perfil", [])

    if perfil2:
        st.write(
            "**Perfil aromático:**",
            ", ".join(perfil2),
        )
    else:
        st.write(
            "**Perfil aromático:** Não informado"
        )

    if moleculas2:

        st.write(
            "**Principais compostos:**"
        )

        st.dataframe(
            pd.DataFrame(
                sorted(moleculas2),
                columns=["Composto aromático"],
            ),
            hide_index=True,
            use_container_width=True,
        )

    else:

        st.info(
            "Nenhum composto aromático encontrado."
        )


# ------------------------------------------------------------------------
# MOLÉCULAS COMPARTILHADAS
# ------------------------------------------------------------------------

st.divider()

st.subheader(
    "🧬 Moléculas compartilhadas"
)


if compartilhadas:

    st.write(
        f"Foram encontradas **{len(compartilhadas)} "
        "moléculas compartilhadas** entre os dois ingredientes."
    )

    st.dataframe(
        pd.DataFrame(
            compartilhadas,
            columns=["Composto aromático compartilhado"],
        ),
        hide_index=True,
        use_container_width=True,
    )

else:

    st.info(
        "Nenhuma molécula idêntica foi encontrada "
        "entre os principais compostos listados."
    )


# ------------------------------------------------------------------------
# GEMINI
# ------------------------------------------------------------------------

st.divider()

st.subheader(
    "👨‍🍳 Chef Tradutor"
)


with st.spinner(
    "🤖 O Chef Tradutor está analisando a combinação..."
):

    resultado_ia = analisar_harmonizacao(
        dados1,
        dados2,
        api_key,
    )


st.markdown(resultado_ia)
```

# ============================================================================

# ESTADO INICIAL

# ============================================================================

else:

```
st.info(
    "Escolha uma combinação de exemplo ou digite dois ingredientes "
    "em inglês para começar."
)
```

```

### Depois de substituir

No GitHub, faça:

**`app.py` → Edit → apaga tudo → cola o código acima → Commit changes.**

O seu repositório atualmente tem justamente `app.py` e `requirements.txt` na raiz, então não precisa mudar a estrutura do projeto.

Depois, no Streamlit Cloud:

**Manage app → Reboot app**

E deixe o `requirements.txt` como está — ele já contém `streamlit`, `requests`, `google-genai` e `pandas`.

### ⚠️ Uma coisa importante

Se depois disso o aplicativo **abrir**, mas aparecer algo como:

> "Não encontrei dados para strawberry no FlavorDB"

**não mexa no código ainda.**

Isso significará que passamos da primeira barreira — Python/Streamlit/Gemini — e o problema estará especificamente na integração com o FlavorDB2. Aí eu ajusto essa parte com você.

Se aparecer **qualquer erro vermelho**, me manda exatamente o erro. A partir desse código, ele já vai estar muito mais fácil de diagnosticar.
```
