"""
vector_store.py — ChromaDB (local dev) / Pinecone (prod) vector store wrapper.

Provides two public functions used by BaseAgent helpers:
    embed_and_store(docs, metadata, collection)  → None
    similarity_search(query, collection, k)      → list[dict]

Configuration
─────────────
Set USE_PINECONE=true in .env to switch from local ChromaDB to Pinecone.

Local dev (ChromaDB):   No extra setup; persists to ./chroma_db/ by default.
Production (Pinecone):  Requires PINECONE_API_KEY and PINECONE_ENV in .env.

Collection names used by agents
────────────────────────────────
"events"     → historical event records (used by Pricing + Revenue agents)
"sponsors"   → sponsor profiles discovered in past runs
"speakers"   → speaker profiles + past talk topics
"venues"     → venue data for semantic re-use across queries
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_USE_PINECONE = os.getenv("USE_PINECONE", "false").lower() == "true"
_CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")


def _get_chroma_collection(collection: str) -> Any:
    """Return (or create) a ChromaDB collection by name using OpenAI embeddings."""
    import chromadb  # type: ignore[import-untyped]
    from chromadb.utils import embedding_functions

    # Use OpenAI to avoid blocking 1GB local ONNX model downloads
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name="text-embedding-3-small"
    )

    client = chromadb.PersistentClient(path=_CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(
        name=collection,
        embedding_function=openai_ef
    )


def embed_and_store(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str = "events",
) -> None:
    """Embed documents and upsert them into the vector store.

    Each document is embedded using OpenAI text-embedding-3-small and stored
    alongside its metadata for later retrieval.

    Args:
        docs:       List of text strings to embed and store.
        metadata:   Parallel list of metadata dicts (same length as docs).
                    Each dict can contain any JSON-serialisable keys.
        collection: Target collection name (ChromaDB) or namespace (Pinecone).

    Raises:
        ValueError: If docs and metadata have different lengths.
        OSError:    If OPENAI_API_KEY is not set.

    Usage::

        embed_and_store(
            docs=["TechCorp sponsors AI events in Europe"],
            metadata=[{"name": "TechCorp", "tier": "Gold"}],
            collection="sponsors",
        )
    """
    if len(docs) != len(metadata):
        raise ValueError(
            f"docs ({len(docs)}) and metadata ({len(metadata)}) must have the same length"
        )
    if not docs:
        return

    if _USE_PINECONE:
        _pinecone_upsert(docs, metadata, collection)
    else:
        _chroma_upsert(docs, metadata, collection)


def similarity_search(
    query: str,
    collection: str = "events",
    k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve the k most semantically similar documents to a query.

    Args:
        query:      Natural language query string.
        collection: Collection / namespace to search in.
        k:          Number of results to return.

    Returns:
        List of dicts, each with:
            - "document": the original text that was stored
            - "metadata": the metadata dict that was stored alongside it
            - "distance": cosine distance (0 = identical, 2 = opposite)

    Usage::

        results = similarity_search("AI sponsors Europe", collection="sponsors", k=3)
        for r in results:
            print(r["metadata"]["name"], r["distance"])
    """
    if _USE_PINECONE:
        return _pinecone_query(query, collection, k)
    return _chroma_query(query, collection, k)


# ── ChromaDB backend ──────────────────────────────────────────────────────────


def _chroma_upsert(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str,
) -> None:
    import hashlib

    coll = _get_chroma_collection(collection)
    ids = [hashlib.md5(d.encode()).hexdigest() for d in docs]
    coll.upsert(documents=docs, metadatas=metadata, ids=ids)


def _chroma_query(query: str, collection: str, k: int) -> list[dict[str, Any]]:
    coll = _get_chroma_collection(collection)
    results = coll.query(
        query_texts=[query], n_results=k, include=["documents", "metadatas", "distances"]
    )
    output: list[dict[str, Any]] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        strict=True,
    ):
        output.append({"document": doc, "metadata": meta, "distance": dist})
    return output


# ── Pinecone backend (production) ─────────────────────────────────────────────


def _get_pinecone_index(collection: str) -> Any:
    from pinecone import Pinecone  # type: ignore[import-untyped]

    api_key = os.getenv("PINECONE_API_KEY", "")
    if not api_key:
        raise OSError("PINECONE_API_KEY is not set — add it to your .env file.")
    pc = Pinecone(api_key=api_key)
    return pc.Index(collection)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using OpenAI text-embedding-3-small."""
    from openai import OpenAI  # type: ignore[import-untyped]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def _pinecone_upsert(
    docs: list[str],
    metadata: list[dict[str, Any]],
    collection: str,
) -> None:
    import hashlib

    index = _get_pinecone_index(collection)
    embeddings = _embed_texts(docs)
    vectors = [
        {
            "id": hashlib.md5(doc.encode()).hexdigest(),
            "values": emb,
            "metadata": {**meta, "_document": doc},
        }
        for doc, emb, meta in zip(docs, embeddings, metadata, strict=True)
    ]
    index.upsert(vectors=vectors)


def _pinecone_query(query: str, collection: str, k: int) -> list[dict[str, Any]]:
    index = _get_pinecone_index(collection)
    emb = _embed_texts([query])[0]
    res = index.query(vector=emb, top_k=k, include_metadata=True)
    return [
        {
            "document": match["metadata"].pop("_document", ""),
            "metadata": match["metadata"],
            "distance": 1.0 - match["score"],  # convert similarity to distance
        }
        for match in res["matches"]
    ]
