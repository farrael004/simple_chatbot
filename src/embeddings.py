import streamlit as st
from typing import List, Tuple
import math
import hashlib


# Lightweight embeddings via sentence-transformers (small model). Falls back to a tiny TF-IDF style embed if unavailable.
try:
    from fast_sentence_transformers import (
        FastSentenceTransformer as SentenceTransformer,
    )

    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SentenceTransformer = None  # type: ignore
    _SENTENCE_TRANSFORMERS_AVAILABLE = False


def _split_into_chunks(
    text: str, chunk_size: int = 800, overlap: int = 120
) -> List[str]:
    if not text:
        return []
    # Split by paragraphs first to keep boundaries reasonable
    paras = [p.strip() for p in text.splitlines()]
    buf = ""
    chunks: List[str] = []
    for p in paras:
        if not p:
            continue
        # If adding the paragraph exceeds size, flush buffer to chunks with overlap handling
        if len(buf) + len(p) + 1 > chunk_size and buf:
            chunks.append(buf.strip())
            # create overlap by taking tail of the previous chunk
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = (tail + " " + p).strip()
        else:
            if buf:
                buf += "\n" + p
            else:
                buf = p
        # If buffer grows significantly beyond size, force split
        while len(buf) > chunk_size + overlap:
            chunks.append(buf[:chunk_size].strip())
            buf = (
                (buf[chunk_size - overlap :]).strip()
                if overlap > 0
                else buf[chunk_size:].strip()
            )
    if buf:
        chunks.append(buf.strip())
    # Filter very tiny chunks
    return [c for c in chunks if len(c) > 20]


def rag_chunk_texts(
    uploaded_texts: List[str], chunk_size: int = 800, overlap: int = 120
) -> List[Tuple[str, int, int]]:
    """
    Returns list of tuples: (chunk_text, doc_index (1-based), chunk_index (1-based))
    """
    chunks: List[Tuple[str, int, int]] = []
    for di, text in enumerate(uploaded_texts, 1):
        parts = _split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
        for ci, part in enumerate(parts, 1):
            chunks.append((part, di, ci))
    return chunks


# ======================
# RAG: Embedding utilities
# ======================
def _get_embedder():
    """
    Returns a callable that maps List[str] -> List[List[float]].
    Caches the model in st.session_state for efficiency.
    """
    if "_embedder" in st.session_state:
        return st.session_state["_embedder"]

    if _SENTENCE_TRANSFORMERS_AVAILABLE:
        # Small, fast, widely available model
        model_name = "all-MiniLM-L6-v2"
        model = SentenceTransformer(model_name)

        def _embed(texts: List[str]) -> List[List[float]]:
            return [list(v) for v in model.encode(texts, normalize_embeddings=True)]

        st.session_state["_embedder"] = _embed
        return _embed

    # Fallback: extremely light bag-of-words hashed vector with l2 norm, purely local
    def _hash_embedding(s: str, dim: int = 512) -> List[float]:
        vec = [0.0] * dim
        tokens = s.lower().split()
        if not tokens:
            return vec
        for tok in tokens:
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            vec[idx] += 1.0
        # l2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def _embed(texts: List[str]) -> List[List[float]]:
        return [_hash_embedding(t) for t in texts]

    st.session_state["_embedder"] = _embed
    return _embed


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


# ======================
# RAG: Index build and search
# ======================
def rag_build_index(
    uploaded_texts: List[str], chunk_size: int = 800, overlap: int = 120
):
    """
    Build (and cache) a simple in-memory index with embeddings.
    Stores in st.session_state["rag_index"] = {"chunks": [...], "embeddings": [...]}.
    """
    chunks = rag_chunk_texts(uploaded_texts, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        st.session_state["rag_index"] = {"chunks": [], "embeddings": []}
        return st.session_state["rag_index"]

    embed = _get_embedder()
    texts = [c[0] for c in chunks]
    with st.spinner("Indexing uploaded documents..."):
        embs = embed(texts)

    index = {"chunks": chunks, "embeddings": embs}
    st.session_state["rag_index"] = index
    return index


def _ensure_index(uploaded_texts: List[str]):
    """
    Ensure we have an index corresponding to current uploaded_texts.
    If texts changed in length or content hash, rebuild.
    """
    key = "_rag_docs_hash"
    digest = (
        hashlib.sha256(("\n\n---\n\n".join(uploaded_texts)).encode("utf-8")).hexdigest()
        if uploaded_texts
        else ""
    )
    if "rag_index" not in st.session_state or st.session_state.get(key) != digest:
        rag_build_index(uploaded_texts)
        st.session_state[key] = digest
    return st.session_state.get("rag_index", {"chunks": [], "embeddings": []})


def rag_search(
    query: str, uploaded_texts: List[str], top_k: int = 5
) -> Tuple[str, List[Tuple[int, int]]]:
    index = _ensure_index(uploaded_texts)
    chunks: List[Tuple[str, int, int]] = index.get("chunks", [])
    embs: List[List[float]] = index.get("embeddings", [])
    if not chunks or not embs:
        return "", []

    embed = _get_embedder()
    q_emb = embed([query])[0]

    scored = []
    for (text, d_i, c_i), emb in zip(chunks, embs):
        sim = _cosine(q_emb, emb)
        scored.append((sim, text, d_i, c_i))
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = scored[: max(1, top_k)]
    refs = [(d_i, c_i) for _, __, d_i, c_i in selected]

    # Build concise context with citations
    lines = []
    for rank, (sim, text, d_i, c_i) in enumerate(selected, 1):
        lines.append(f"[D{d_i}-{c_i}] (sim={sim:.3f})\n{text}")
    return lines, refs
