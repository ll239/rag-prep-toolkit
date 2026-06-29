import streamlit as st
import anthropic
import json
import csv
import io
import os
import fitz
from sentence_transformers import SentenceTransformer

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="RAG Prep Toolkit",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 RAG Prep Toolkit")
st.markdown("*Upload your documents, let Claude propose a schema and generate embeddings — ready to plug into any RAG stack.*")

# -------------------- SESSION STATE --------------------
if "proposed_schema" not in st.session_state:
    st.session_state.proposed_schema = None
if "semantic_chunks" not in st.session_state:
    st.session_state.semantic_chunks = None
if "embeddings" not in st.session_state:
    st.session_state.embeddings = None
if "final_schema" not in st.session_state:
    st.session_state.final_schema = None

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-..."
    )
    st.markdown("*Your key is never stored — only used for this session.*")
    st.divider()
    st.markdown("**How it works:**")
    st.markdown("1. Upload your document")
    st.markdown("2. Claude proposes keywords and schema")
    st.markdown("3. Confirm or edit in plain English")
    st.markdown("4. Download SQL schema + embeddings + Python starter")
    st.divider()
    st.markdown("**Supported file types:** TXT, JSON, PDF, CSV")


# -------------------- FILE READING --------------------
def read_file(uploaded_file):
    file_type = uploaded_file.name.split(".")[-1].lower()
    if file_type == "txt":
        return uploaded_file.read().decode("utf-8", errors="ignore")
    elif file_type == "json":
        data = json.load(uploaded_file)
        return json.dumps(data, indent=2)
    elif file_type == "pdf":
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    elif file_type == "csv":
        content = uploaded_file.read().decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        return "\n".join([",".join(row) for row in rows])
    else:
        st.error(f"Unsupported file type: {file_type}")
        return None


# -------------------- CLAUDE SCHEMA ANALYSIS --------------------
def analyze_document(content, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are a data architect helping prepare documents for a RAG system.

Analyze this document and identify:

1. KEYWORDS: Structured data for SQL database (IDs, codes, dates, names, categories)
2. SEMANTIC CONTENT: Unstructured text for embedding (narrative, descriptions)
3. PROPOSED SCHEMA: SQL column names and types

Respond in this EXACT JSON format:
{{
  "keywords": [
    {{"column_name": "ticket_id", "data_type": "VARCHAR(50)", "example_values": ["TKT-001", "TKT-002"], "description": "Unique ticket identifier"}}
  ],
  "semantic_content": "Description of what will be embedded",
  "table_name": "suggested_table_name",
  "reasoning": "Brief explanation of your choices"
}}

Document:
{content[:3000]}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.split("```")[0]
    return json.loads(raw.strip())


# -------------------- GENERATE FINAL SCHEMA --------------------
def generate_final_schema(analysis, user_instructions, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are a SQL expert. Generate a CREATE TABLE statement based on this schema.

Proposed schema:
{json.dumps(analysis, indent=2)}

User instructions: {user_instructions if user_instructions else "Use standard SQL syntax"}

Generate:
1. A clean CREATE TABLE statement
2. An INSERT INTO template with placeholder values
3. 2-3 useful SELECT queries

Return only the SQL, no explanations."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# -------------------- GENERATE EMBEDDINGS --------------------
def generate_embeddings(content, analysis):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    words = content.split()
    chunk_size = 150
    overlap = 30
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap

    embeddings_list = model.encode(chunks).tolist()
    result = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
        result.append({
            "id": f"chunk_{i+1}",
            "text": chunk,
            "embedding": embedding,
            "metadata": {
                "chunk_index": i + 1,
                "total_chunks": len(chunks),
                "table_reference": analysis.get("table_name", "unknown")
            }
        })
    return result


# -------------------- GENERATE PYTHON FILE --------------------
def generate_python_file(analysis, embeddings, final_schema):
    table_name = analysis.get("table_name", "my_table")
    columns = analysis.get("keywords", [])
    column_names = [col["column_name"] for col in columns]
    search_conditions = " OR ".join([f"{col} LIKE ?" for col in column_names])
    num_columns = len(column_names)
    columns_str = ", ".join(column_names)
    embeddings_preview = json.dumps(embeddings[:2], indent=2)
    total_chunks = len(embeddings)

    lines = [
        "# ============================================================",
        "# Auto generated by RAG Prep Toolkit",
        "# github.com/ll239",
        "#",
        "# Drop this into your project and customize:",
        "# - Swap sqlite3 for snowflake.connector, psycopg2, etc",
        "# - Swap chromadb for pinecone, weaviate, astradb, etc",
        "# ============================================================",
        "",
        "import sqlite3",
        "import json",
        "from sentence_transformers import SentenceTransformer",
        "import chromadb",
        "",
        "# -------------------- CONFIG --------------------",
        'DB_PATH = "your_database.db"',
        f'COLLECTION_NAME = "{table_name}_embeddings"',
        'EMBEDDING_MODEL = "all-MiniLM-L6-v2"',
        "",
        "# -------------------- SCHEMA --------------------",
        "CREATE_TABLE_SQL = '''",
        final_schema,
        "'''",
        "",
        "def create_table():",
        "    conn = sqlite3.connect(DB_PATH)",
        "    conn.executescript(CREATE_TABLE_SQL)",
        "    conn.commit()",
        "    conn.close()",
        f'    print("Table {table_name} created successfully")',
        "",
        "# -------------------- EMBEDDINGS --------------------",
        f"# {total_chunks} total chunks — full set in embeddings.json",
        f"# Columns detected: {columns_str}",
        "",
        f"EMBEDDINGS = {embeddings_preview}",
        "",
        "def load_embeddings_to_chromadb():",
        '    """Load embeddings into ChromaDB — swap for your vector DB"""',
        "    client = chromadb.Client()",
        "    collection = client.get_or_create_collection(COLLECTION_NAME)",
        "    for chunk in EMBEDDINGS:",
        "        collection.add(",
        '            ids=[chunk["id"]],',
        '            documents=[chunk["text"]],',
        '            embeddings=[chunk["embedding"]],',
        '            metadatas=[chunk["metadata"]]',
        "        )",
        "    print(f'Loaded {len(EMBEDDINGS)} chunks into ChromaDB')",
        "    return collection",
        "",
        "# -------------------- HYBRID SEARCH --------------------",
        "def keyword_search(query, limit=10):",
        '    """Search structured DB for exact keyword matches"""',
        "    conn = sqlite3.connect(DB_PATH)",
        "    cur = conn.cursor()",
        f"    cur.execute('SELECT * FROM {table_name} WHERE {search_conditions} LIMIT ?',",
        f"        tuple([f'%{{query}}%' for _ in range({num_columns})] + [limit]))",
        "    results = cur.fetchall()",
        "    cols = [desc[0] for desc in cur.description]",
        "    conn.close()",
        "    return [dict(zip(cols, row)) for row in results]",
        "",
        "def semantic_search(query, top_k=3):",
        '    """Search vector DB for semantically similar content"""',
        "    model = SentenceTransformer(EMBEDDING_MODEL)",
        "    query_embedding = model.encode([query]).tolist()",
        "    client = chromadb.Client()",
        "    collection = client.get_collection(COLLECTION_NAME)",
        "    results = collection.query(query_embeddings=query_embedding, n_results=top_k)",
        '    return results["documents"][0] if results["documents"] else []',
        "",
        "def hybrid_search(query, top_k=3):",
        "    return {",
        '        "keyword_matches": keyword_search(query),',
        '        "semantic_matches": semantic_search(query, top_k),',
        '        "query": query',
        "    }",
        "",
        "if __name__ == '__main__':",
        "    create_table()",
        "    load_embeddings_to_chromadb()",
        '    results = hybrid_search("your search query here")',
        '    print("Keyword matches:", results["keyword_matches"])',
        '    print("Semantic matches:", results["semantic_matches"])',
    ]
    return "\n".join(lines)


# -------------------- MAIN APP --------------------
st.divider()

st.header("Step 1 — Upload your document")
uploaded_files = st.file_uploader(
    "Choose files",
    type=["txt", "json", "pdf", "csv"],
    accept_multiple_files=True,
    help="Upload one or more documents to prepare for RAG"
)

if uploaded_files and api_key:
    all_content = []
    for uploaded_file in uploaded_files:
        file_content = read_file(uploaded_file)
        if file_content:
            all_content.append(f"--- File: {uploaded_file.name} ---\n{file_content}")

    content = "\n\n".join(all_content)

    if content:
        with st.expander(f"Preview combined content ({len(uploaded_files)} files)", expanded=False):
            st.text(content[:1000] + "..." if len(content) > 1000 else content)

        st.divider()

        # STEP 2
        st.header("Step 2 — Claude analyzes your document")
        if st.button("Analyze Document", type="primary"):
            with st.spinner("Claude is analyzing your document..."):
                try:
                    analysis = analyze_document(content, api_key)
                    st.session_state.proposed_schema = analysis
                    st.session_state.semantic_chunks = content
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

        if st.session_state.proposed_schema:
            analysis = st.session_state.proposed_schema

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Proposed SQL columns")
                st.markdown(f"**Table name:** `{analysis.get('table_name', 'my_table')}`")
                for kw in analysis.get("keywords", []):
                    st.markdown(f"**{kw['column_name']}** ({kw['data_type']})")
                    st.markdown(f"*{kw['description']}*")
                    st.markdown(f"Examples: {', '.join([str(v) for v in kw['example_values'][:3]])}")
                    st.divider()

            with col2:
                st.subheader("Semantic content for embedding")
                st.info(analysis.get("semantic_content", ""))
                st.subheader("Reasoning")
                st.markdown(analysis.get("reasoning", ""))

            st.divider()

            # STEP 3
            st.header("Step 3 — Confirm or customize")
            st.markdown("Tell Claude any changes in plain English:")
            user_instructions = st.text_area(
                "Your instructions (optional)",
                placeholder="e.g. 'Use Snowflake syntax', 'Add an agent_name column', 'Use MySQL with InnoDB engine'",
                height=100
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Generate SQL Schema", type="primary"):
                    with st.spinner("Generating SQL schema..."):
                        try:
                            final_schema = generate_final_schema(analysis, user_instructions, api_key)
                            st.session_state.final_schema = final_schema
                        except Exception as e:
                            st.error(f"Schema generation failed: {e}")

            with col2:
                if st.button("Generate Embeddings", type="secondary"):
                    with st.spinner("Generating embeddings... this may take a moment"):
                        try:
                            embeddings = generate_embeddings(content, analysis)
                            st.session_state.embeddings = embeddings
                        except Exception as e:
                            st.error(f"Embedding generation failed: {e}")

            st.divider()

            # STEP 4
            st.header("Step 4 — Download your outputs")
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.session_state.final_schema:
                    st.subheader("SQL Schema")
                    st.code(st.session_state.final_schema, language="sql")
                    st.download_button(
                        label="Download schema.sql",
                        data=st.session_state.final_schema,
                        file_name="schema.sql",
                        mime="text/plain"
                    )

            with col2:
                if st.session_state.embeddings:
                    embeddings_json = json.dumps(st.session_state.embeddings, indent=2)
                    st.subheader("Embeddings")
                    st.markdown(f"**{len(st.session_state.embeddings)} chunks generated**")
                    st.markdown("Ready to load into Pinecone, Weaviate, ChromaDB, AstraDB — any vector DB.")
                    with st.expander("Preview first chunk"):
                        preview = st.session_state.embeddings[0].copy()
                        preview["embedding"] = preview["embedding"][:5] + ["..."]
                        st.json(preview)
                    st.download_button(
                        label="Download embeddings.json",
                        data=embeddings_json,
                        file_name="embeddings.json",
                        mime="application/json"
                    )

            with col3:
                if st.session_state.final_schema and st.session_state.embeddings:
                    st.subheader("Python Starter File")
                    st.markdown("Drop into your project. Swap DB connectors as needed.")
                    python_code = generate_python_file(
                        st.session_state.proposed_schema,
                        st.session_state.embeddings,
                        st.session_state.final_schema
                    )
                    st.download_button(
                        label="Download rag_starter.py",
                        data=python_code,
                        file_name="rag_starter.py",
                        mime="text/plain"
                    )
                    with st.expander("Preview"):
                        st.code(python_code[:500] + "...", language="python")

elif uploaded_files and not api_key:
    st.warning("Please enter your Anthropic API key in the sidebar to continue.")
elif not uploaded_files and api_key:
    st.info("Upload a document to get started.")
else:
    st.info("Enter your API key in the sidebar and upload a document to get started.")

# -------------------- FOOTER --------------------
st.divider()
st.markdown("*Built by Lina Devakumar Louis — github.com/ll239*")