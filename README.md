# RAG Prep Toolkit

A Streamlit app that prepares your documents for hybrid RAG search — upload your files, let Claude propose a schema, and download ready-to-use SQL schema, embeddings, and a Python starter file.

<img width="1402" height="1122" alt="ChatGPT Image Jun 29, 2026, 03_10_48 PM" src="https://github.com/user-attachments/assets/473d9119-3d36-45ad-83ba-6d0e3742d121" />


## Why I built this

After building multiple RAG systems I kept noticing the same pattern — the best retrieval always came from hybrid search, combining keyword search for structured data with semantic search for unstructured content. But every time I had to manually figure out what should go into SQL vs what should be embedded.

This tool automates that decision. Upload your documents, Claude analyzes them and proposes the split, you confirm or adjust in plain English, and you get everything you need to plug into your own stack.

## What it does

- Upload TXT, JSON, PDF, or CSV files (multiple files supported)
- Claude reads your documents and proposes which fields should be keywords (SQL) and which should be embedded (vector DB)
- You confirm or customize the schema in plain English — no code needed
- Download three ready to use outputs:
  - schema.sql — CREATE TABLE statement in your preferred dialect (MySQL, Snowflake, Postgres — just tell Claude)
  - embeddings.json — chunks with embeddings ready to load into any vector DB
  - rag_starter.py — drop-in Python file with hybrid search already wired up

## How to use it

Go to the deployed app, enter your Anthropic API key, upload your documents and follow the steps.

Your API key is never stored — it is only used for your session and you pay your own usage.

## Run it locally

    git clone https://github.com/ll239/rag-prep-toolkit.git
    cd rag-prep-toolkit
    pip install -r requirements.txt
    streamlit run app.py

## Stack

- Streamlit
- Anthropic Claude claude-sonnet-4-5
- Sentence Transformers all-MiniLM-L6-v2
- PyMuPDF for PDF reading

## The outputs plug into any stack

The schema.sql works with MySQL, Snowflake, Postgres, SQLite — just tell Claude which dialect you want.
The embeddings.json works with Pinecone, Weaviate, ChromaDB, AstraDB — paste and load.
The rag_starter.py gives you a working hybrid search function to drop into your project.

## Author

Lina Devakumar Louis
github.com/ll239
