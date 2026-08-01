"""
Embedding generation for VeriSight RAG.

Handles text chunking for long documents and provides a configurable
embedding interface. By default uses ChromaDB's built-in embedding
function (all-MiniLM-L6-v2).
"""

from typing import List
from verisight.utils.logger import get_logger

logger = get_logger("embeddings")

# Maximum characters per chunk for embedding
MAX_CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200


def chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks suitable for embedding.

    Args:
        text: Input text to chunk.
        max_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= max_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_size

        # Try to break at a newline or sentence boundary
        if end < len(text):
            # Look for a good break point
            for break_char in ["\n\n", "\n", ". ", "; ", ", "]:
                break_pos = text.rfind(break_char, start + max_size // 2, end)
                if break_pos > start:
                    end = break_pos + len(break_char)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap
        if start >= len(text):
            break

    return chunks


def prepare_document_for_embedding(
    content: str,
    doc_type: str,
    identifier: str,
) -> List[dict]:
    """
    Prepare a document for storage in ChromaDB.

    Chunks the document and adds metadata to each chunk.

    Args:
        content: Document text.
        doc_type: Type of document (spec, rtl, tb, log, etc.).
        identifier: Document identifier (filename, etc.).

    Returns:
        List of dicts with 'id', 'document', and 'metadata' keys.
    """
    chunks = chunk_text(content)
    prepared = []

    for i, chunk in enumerate(chunks):
        prepared.append({
            "id": f"{doc_type}_{identifier}_chunk{i}",
            "document": chunk,
            "metadata": {
                "type": doc_type,
                "identifier": identifier,
                "chunk_index": str(i),
                "total_chunks": str(len(chunks)),
            }
        })

    return prepared
