"""File upload tools — upload files for background parsing and embedding."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from fastmcp import Context
from fastmcp.tools import tool
from loguru import logger
from sqlalchemy import select

from solomons_library.config import settings
from solomons_library.db import get_async_session_factory
from solomons_library.models import FileUpload, UploadStatus
from solomons_library.tools.embed import _generate_embedding, _resolve_agent, _split_into_chunks
from solomons_library.tools.parsers import detect_mime_type, parse_file

# Base directory for file storage
UPLOADS_DIR = Path("uploads")


def _ensure_upload_dir(project_name: str) -> Path:
    """Create and return the upload directory for a project."""
    upload_dir = UPLOADS_DIR / project_name
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


@tool(tags={"uploads", "write"})
async def upload_file(
    filename: str,
    file_content_base64: str,
    user: str,
    project_name: str | None = None,
    agent: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Upload a file for background parsing and embedding.

    The file is saved to disk and a background task is enqueued to parse the
    file content and generate embeddings. Returns immediately with an upload ID
    that can be used to track progress via get_upload_status.

    Args:
        filename: Original filename (e.g., "report.pdf"). Used to detect file type.
        file_content_base64: Base64-encoded file content.
        user: Username of the uploader.
        project_name: Project to store embeddings under. Defaults to server config.
        agent: Optional agent identifier. Auto-detected from MCP clientInfo if omitted.
    """
    project_name = project_name or settings.PROJECT_NAME
    resolved_agent = _resolve_agent(agent, ctx)

    # Detect MIME type from filename
    mime_type = detect_mime_type(filename)
    if mime_type == "application/octet-stream":
        return {"error": f"Unsupported file type for '{filename}'. Supported: TXT, MD, CSV, PDF, DOCX, HTML, JSON, YAML"}

    # Decode base64 content
    try:
        file_bytes = base64.b64decode(file_content_base64)
    except Exception as e:
        return {"error": f"Invalid base64 content: {e}"}

    # Save file to disk
    upload_dir = _ensure_upload_dir(project_name)
    safe_filename = f"{uuid.uuid4().hex[:12]}_{filename}"
    file_path = upload_dir / safe_filename
    file_path.write_bytes(file_bytes)

    if ctx:
        await ctx.info(f"File saved: {file_path} ({len(file_bytes)} bytes)")

    # Create FileUpload record
    async_session = get_async_session_factory()
    async with async_session() as session:
        upload = FileUpload(
            filename=filename,
            file_path=str(file_path),
            mime_type=mime_type,
            file_size=len(file_bytes),
            status=UploadStatus.PENDING.value,
            project_name=project_name,
            user=user,
            agent=resolved_agent,
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
        upload_id = upload.id

    logger.info(f"File upload #{upload_id} created: {filename} ({mime_type}, {len(file_bytes)} bytes)")

    # Enqueue background processing task
    if ctx:
        await ctx.info(f"Upload #{upload_id} queued for background processing")

    # Call the background task tool — FastMCP Docket will enqueue it
    await process_upload(upload_id=upload_id, ctx=ctx)

    return {
        "upload_id": upload_id,
        "filename": filename,
        "mime_type": mime_type,
        "file_size": len(file_bytes),
        "status": "pending",
        "message": f"File queued for processing. Use get_upload_status(upload_id={upload_id}) to track progress.",
    }


@tool(task=True, tags={"uploads", "background"})
async def process_upload(
    upload_id: int,
    ctx: Context | None = None,
) -> dict:
    """Background task: parse an uploaded file and generate embeddings.

    This tool runs as a Docket background task. It reads the file from disk,
    parses it into text, chunks the text, generates embeddings, and stores
    them in the database.

    Args:
        upload_id: ID of the FileUpload record to process.
    """
    from solomons_library.models import Embedding

    async_session = get_async_session_factory()

    # Load the upload record
    async with async_session() as session:
        upload = await session.get(FileUpload, upload_id)
        if not upload:
            return {"error": f"Upload #{upload_id} not found"}

        # Mark as processing
        upload.status = UploadStatus.PROCESSING.value
        await session.commit()

        # Capture fields we need outside the session
        upload_filename = upload.filename
        upload_file_path = upload.file_path
        upload_mime_type = upload.mime_type
        upload_project_name = upload.project_name
        upload_user = upload.user
        upload_agent = upload.agent

    logger.info(f"Processing upload #{upload_id}: {upload_filename}")

    if ctx:
        await ctx.report_progress(progress=0, total=100)
        await ctx.info(f"Processing upload #{upload_id}: {upload_filename}")

    try:
        # Step 1: Parse the file
        text_content = parse_file(upload_file_path, upload_mime_type)
        if not text_content.strip():
            raise ValueError("File produced no extractable text")

        if ctx:
            await ctx.report_progress(progress=20, total=100)
            await ctx.info(f"Parsed {len(text_content)} chars from {upload_filename}")

        # Step 2: Chunk the text
        chunks = _split_into_chunks(text_content)
        total_chunks = len(chunks)

        if ctx:
            await ctx.report_progress(progress=30, total=100)
            await ctx.info(f"Split into {total_chunks} chunk(s)")

        # Step 3: Generate embeddings in parallel
        import asyncio

        embedding_tasks = [_generate_embedding(chunk) for chunk in chunks]
        vectors_and_models = await asyncio.gather(*embedding_tasks)

        if ctx:
            await ctx.report_progress(progress=70, total=100)
            await ctx.info(f"Generated {total_chunks} embedding(s), storing...")

        model_name = vectors_and_models[0][1] if vectors_and_models else ""

        # Step 4: Store embeddings in parallel
        async def _store_chunk(i: int, chunk: str, vector: list[float], model: str) -> int:
            chunk_source = f"upload:{upload_id}:{upload_filename}"
            if total_chunks > 1:
                chunk_source = f"{chunk_source}#chunk-{i + 1}"

            async with async_session() as sess:
                emb = Embedding(
                    text=chunk,
                    source=chunk_source,
                    model=model,
                    project_name=upload_project_name,
                    user=upload_user,
                    agent=upload_agent,
                    embedding=vector,
                )
                sess.add(emb)
                await sess.commit()
                await sess.refresh(emb)
                return emb.id

        store_tasks = [
            _store_chunk(i, chunk, vector, model)
            for i, (chunk, (vector, model)) in enumerate(zip(chunks, vectors_and_models))
        ]
        embedding_ids = await asyncio.gather(*store_tasks)

        # Step 5: Mark upload as completed
        async with async_session() as session:
            rec = await session.get(FileUpload, upload_id)
            if rec:
                rec.status = UploadStatus.COMPLETED.value
                rec.chunk_count = total_chunks
                await session.commit()

        if ctx:
            await ctx.report_progress(progress=100, total=100)
            await ctx.info(f"Upload #{upload_id} completed: {total_chunks} embeddings stored")

        logger.info(f"Upload #{upload_id} completed: {total_chunks} chunks, {len(text_content)} chars")

        return {
            "upload_id": upload_id,
            "status": "completed",
            "chunks": total_chunks,
            "model": model_name,
            "embedding_ids": embedding_ids,
            "text_length": len(text_content),
        }

    except Exception as e:
        logger.error(f"Upload #{upload_id} failed: {e}")

        # Mark as failed with error message
        async with async_session() as session:
            rec = await session.get(FileUpload, upload_id)
            if rec:
                rec.status = UploadStatus.FAILED.value
                rec.error_message = str(e)[:2000]
                await session.commit()

        if ctx:
            await ctx.error(f"Upload #{upload_id} failed: {e}")

        return {
            "upload_id": upload_id,
            "status": "failed",
            "error": str(e),
        }


@tool(tags={"uploads", "read"}, annotations={"readOnlyHint": True})
async def get_upload_status(
    upload_id: int,
    ctx: Context | None = None,
) -> dict:
    """Check the status of a file upload.

    Args:
        upload_id: The upload ID returned by upload_file.
    """
    async_session = get_async_session_factory()
    async with async_session() as session:
        upload = await session.get(FileUpload, upload_id)
        if not upload:
            return {"error": f"Upload #{upload_id} not found"}

    if ctx:
        await ctx.info(f"Upload #{upload_id}: {upload.status}")

    result = {
        "upload_id": upload.id,
        "filename": upload.filename,
        "mime_type": upload.mime_type,
        "file_size": upload.file_size,
        "status": upload.status,
        "chunk_count": upload.chunk_count,
        "project_name": upload.project_name,
        "user": upload.user,
        "agent": upload.agent,
        "created_at": upload.created_at.isoformat(),
        "updated_at": upload.updated_at.isoformat(),
    }

    if upload.error_message:
        result["error_message"] = upload.error_message

    return result


@tool(tags={"uploads", "read"}, annotations={"readOnlyHint": True})
async def list_uploads(
    project_name: str | None = None,
    status: str | None = None,
    limit: int = 20,
    ctx: Context | None = None,
) -> list[dict]:
    """List recent file uploads with optional filtering.

    Args:
        project_name: Filter by project name. Defaults to all projects.
        status: Filter by status (pending, processing, completed, failed).
        limit: Maximum results to return (default 20).
    """
    async_session = get_async_session_factory()
    async with async_session() as session:
        stmt = select(FileUpload).order_by(FileUpload.created_at.desc()).limit(limit)

        if project_name:
            stmt = stmt.where(FileUpload.project_name == project_name)
        if status:
            stmt = stmt.where(FileUpload.status == status)

        result = await session.execute(stmt)
        uploads = result.scalars().all()

    if ctx:
        await ctx.info(f"Found {len(uploads)} upload(s)")

    return [
        {
            "upload_id": u.id,
            "filename": u.filename,
            "mime_type": u.mime_type,
            "file_size": u.file_size,
            "status": u.status,
            "chunk_count": u.chunk_count,
            "project_name": u.project_name,
            "created_at": u.created_at.isoformat(),
        }
        for u in uploads
    ]
