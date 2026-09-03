SETUP_API_KEY_MD: str = """
Obtenha uma chave gratuita no [Google AI Studio](https://aistudio.google.com/apikey) e:

**Execução local** — crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:

```toml
GEMINI_API_KEY = "SUA_CHAVE_AQUI"
```

**Streamlit Community Cloud** — no app, abra *Settings → Secrets* e adicione a mesma chave.
"""


# ---------------------------------------------------------------------------
# Chave de API (secrets → variáveis de ambiente)
# ---------------------------------------------------------------------------
def get_api_key() -> Optional[str]:
    """Recupera a GEMINI_API_KEY de st.secrets ou do ambiente."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"])
    except Exception:
        pass  # st.secrets indisponível fora do Streamlit
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


# ---------------------------------------------------------------------------
# FlavorDB2 — compostos aromáticos
# ---------------------------------------------------------------------------
def fetch_molecules(ingredient: str) -> Optional[set]:
    """Consulta o FlavorDB2 e devolve o conjunto de compostos aromáticos."""
    try:
        resp = requests.get(
            FLAVORDB_API_URL,
            params={"name": ingredient.strip().lower()},
            headers=HTTP_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        st.warning(f"⚠️ Falha ao consultar o FlavorDB2 para “{ingredient}”: {exc}")
        return None

    # A resposta pode vir como lista ou dicionário — normalizamos:
    entities = payload if isinstance(payload, list) else (
        payload.get("data") or payload.get("entities") or payload.get("results") or []
    )
    if isinstance(entities, dict):
        entities = [entities]

    molecules: set = set()
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        compounds = (
            entity.get("flavor_compounds")
            or entity.get("flavors")
            or entity.get("molecules")
            or entity.get("compounds")
            or []
        )
        for comp in compounds:
            name = comp if isinstance(comp, str) else (
                comp.get("common_name") or comp.get("name") or comp.get("molecule_name")
            )
            if name:
                molecules.add(str(name).strip())
    return molecules or None


# ---------------------------------------------------------------------------
# Afinidade molecular
# ---------------------------------------------------------------------------
def molecular_affinity(mols_a: set, mols_b: set) -> tuple:
    """Moléculas compartilhadas + índice de Jaccard."""
    shared = mols_a & mols_b
    union = mols_a | mols_b
    jaccard = len(shared) / len(union) if union else 0.0
    return shared, jaccard


# ---------------------------------------------------------------------------
# Chef Tradutor (Gemini)
# ---------------------------------------------------------------------------
def ask_chef(ing_a: str, ing_b: str, mols_a: set, mols_b: set, shared: set) -> str:
    api_key = get_api_key()
    if not api_key:
        return SETUP_API_KEY_MD

    def _preview(mols: set) -> str:
        return ", ".join(sorted(mols)[:MAX_MOLECULES]) or "—"

    user_prompt = f"""Ingredientes: {ing_a} × {ing_b}

Compostos aromáticos de {ing_a} ({len(mols_a)} encontrados): {_preview(mols_a)}
Compostos aromáticos de {ing_b} ({len(mols_b)} encontrados): {_preview(mols_b)}

Moléculas COMPARTILHADAS ({len(shared)}) — base da afinidade molecular:
{_preview(shared)}

Índice de Jaccard: {len(shared) / len(mols_a | mols_b):.2f}

Com base nesses dados REAIS, entregue:
## 🧬 Leitura molecular
## 👨‍🍳 Análise sensorial e técnica
## 🍽️ Prato pronto (nome criativo, técnica, temperatura e formato de serviço)
"""

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=CHEF_SYSTEM_PROMPT,
                temperature=0.7,
            ),
        )
    except Exception as exc:
        return f"⚠️ Erro ao chamar o Gemini: {exc}"

    return response.text or "_(o modelo não retornou texto)_"


# ---------------------------------------------------------------------------
# Interface (Streamlit)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Harmonia Molecular", page_icon="🧪", layout="wide")

st.title("🧪 Harmonia Molecular")
st.caption("Afinidade molecular entre dois ingredientes + tradução sensorial por IA.")

if "ing_a" not in st.session_state:
    st.session_state.ing_a, st.session_state.ing_b = "strawberry", "basil"

for col, (label, a, b) in zip(st.columns(len(EXEMPLOS)), EXEMPLOS):
    if col.button(label):
        st.session_state.ing_a, st.session_state.ing_b = a, b

col1, col2 = st.columns(2)
with col1:
    ing_a = st.text_input("Ingrediente A (em inglês)", key="ing_a")
with col2:
    ing_b = st.text_input("Ingrediente B (em inglês)", key="ing_b")

if st.button("🔎 Analisar harmonia", type="primary"):
    if not ing_a.strip() or not ing_b.strip():
        st.error("Preencha os dois ingredientes.")
        st.stop()

    with st.spinner("Consultando compostos no FlavorDB2…"):
        mols_a = fetch_molecules(ing_a)
        mols_b = fetch_molecules(ing_b)

    if not mols_a or not mols_b:
        st.error(
            "Não encontrei compostos aromáticos para um dos ingredientes. "
            "Use nomes em **inglês** (ex.: `strawberry`, não `morango`)."
        )
        st.stop()

    shared, jaccard = molecular_affinity(mols_a, mols_b)

    m1, m2, m3 = st.columns(3)
    m1.metric(f"Compostos · {ing_a}", len(mols_a))
    m2.metric(f"Compostos · {ing_b}", len(mols_b))
    m3.metric("Moléculas em comum", len(shared))

    st.progress(jaccard, text=f"Afinidade molecular (Jaccard): **{jaccard:.2f}**")

    if shared:
        st.subheader("🧬 Moléculas compartilhadas")
        st.dataframe(
            pd.DataFrame(sorted(shared), columns=["Composto aromático"]),
            hide_index=True,
        )
    else:
        st.info("Nenhuma molécula em comum — combinação desafiadora! Veja o que o Chef propõe.")

    with st.spinner("O Chef Tradutor está trabalhando…"):
        st.markdown(ask_chef(ing_a, ing_b, mols_a, mols_b, shared))
else:
    st.info("Escolha um exemplo, digite dois ingredientes e clique em **Analisar harmonia**.")
