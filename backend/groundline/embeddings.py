from __future__ import annotations

import hashlib
import json
import mimetypes

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from groundline.config import Settings
from groundline.ingestion import NormalizedChunk, normalize_file


def document_mime_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


async def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120) as client:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), settings.embedding_batch_size):
            response = await client.post("/api/embed", json={
                "model": settings.embedding_model,
                "input": texts[start:start + settings.embedding_batch_size],
            })
            response.raise_for_status()
            embeddings.extend(response.json()["embeddings"])
        return embeddings


async def embed_chunks(settings: Settings, chunks: list[NormalizedChunk]) -> list[list[float]]:
    return await embed_texts(settings, [chunk.content for chunk in chunks])


async def ingest_file(
    engine: AsyncEngine, settings: Settings, filename: str, content: bytes
) -> dict:
    chunks = [chunk for chunk in normalize_file(filename, content) if chunk.content.strip()]
    embeddings = await embed_chunks(settings, chunks)
    source_id = hashlib.md5(f"{filename}:{len(content)}".encode()).hexdigest()
    revision_id = hashlib.sha256(content).hexdigest()[:32]

    async with engine.begin() as connection:
        await connection.execute(text("""
            INSERT INTO sources (id, name, source_type, uri)
            VALUES (CAST(:id AS uuid), :name, 'file', :uri)
            ON CONFLICT (id) DO NOTHING
        """), {"id": source_id, "name": filename, "uri": filename})
        await connection.execute(text("""
            SELECT id FROM sources WHERE id = CAST(:source_id AS uuid) FOR UPDATE
        """), {"source_id": source_id})
        next_revision = await connection.execute(text("""
            SELECT COALESCE(MAX(revision_number), 0) + 1
            FROM document_revisions
            WHERE source_id = CAST(:source_id AS uuid)
        """), {"source_id": source_id})
        await connection.execute(text("""
            INSERT INTO document_revisions (id, source_id, content_hash, mime_type, revision_number)
            VALUES (CAST(:id AS uuid), CAST(:source_id AS uuid), :hash, :mime, :revision_number)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": revision_id,
            "source_id": source_id,
            "hash": revision_id,
            "mime": document_mime_type(filename),
            "revision_number": next_revision.scalar_one(),
        })
        for ordinal, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True), start=1):
            await connection.execute(text("""
                INSERT INTO chunks (revision_id, ordinal, content, locator, embedding)
                VALUES (CAST(:revision_id AS uuid), :ordinal, :content,
                        CAST(:locator AS jsonb), CAST(:embedding AS vector))
                ON CONFLICT (revision_id, ordinal) DO NOTHING
            """), {
                "revision_id": revision_id,
                "ordinal": ordinal,
                "content": chunk.content,
                "locator": json.dumps(chunk.locator),
                "embedding": "[" + ",".join(map(str, embedding)) + "]",
            })
    return {
        "source_id": source_id,
        "revision_id": revision_id,
        "filename": filename,
        "chunks": len(chunks),
    }
