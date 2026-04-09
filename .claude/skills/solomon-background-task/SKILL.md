---
description: "This skill should be used when creating a Docket background task in Solomon's Library, implementing async processing with progress reporting, building two-phase upload-then-process workflows, or adding task status tracking."
version: 0.1.0
tags:
  - docket
  - redis
  - background-task
  - fastmcp
  - solomon
---

# Solomon's Library — Background Task Pattern

## Architecture

Background tasks use FastMCP's Docket system backed by Redis. A task is an MCP tool marked with `task=True` — when called, FastMCP enqueues it to Redis instead of running it inline. The Docket worker picks it up asynchronously.

```
Client calls upload_file()
  ↓
upload_file() saves record (status=PENDING), calls process_upload()
  ↓
FastMCP Docket enqueues process_upload to Redis
  ↓
Docket worker picks up task, runs process_upload()
  ↓
process_upload() updates status (PROCESSING → COMPLETED/FAILED)
  ↓
Client polls get_upload_status() to track progress
```

Docket URL is set in `server.py`:
```python
os.environ.setdefault("FASTMCP_DOCKET_URL", settings.REDIS_URL)
```

## Background Task Template

### The Trigger Tool (enqueues the task)

```python
@tool(tags={"your_domain", "write"})
async def start_thing(
    name: str,
    user: str,
    project_name: str | None = None,
    agent: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Start processing a thing (enqueues background task).

    Returns immediately with a thing_id for tracking progress.
    """
    project_name = project_name or settings.PROJECT_NAME
    resolved_agent = _resolve_agent(agent, ctx)

    # Create record
    async_session = get_async_session_factory()
    async with async_session() as session:
        record = YourModel(
            name=name,
            status=YourStatus.PENDING.value,
            project_name=project_name,
            user=user,
            agent=resolved_agent,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        thing_id = record.id

    # Enqueue background task — FastMCP Docket handles queueing
    await process_thing(thing_id=thing_id, ctx=ctx)

    return {
        "thing_id": thing_id,
        "status": "pending",
        "message": f"Use get_thing_status(thing_id={thing_id}) to track progress.",
    }
```

### The Task Tool (runs in background via Docket)

```python
@tool(task=True, tags={"your_domain", "background"})
async def process_thing(
    thing_id: int,
    ctx: Context | None = None,
) -> dict:
    """Background task: process a thing.

    This tool runs as a Docket background task. It performs the heavy
    processing and updates status in the database.

    Args:
        thing_id: ID of the record to process.
    """
    async_session = get_async_session_factory()

    # Load the record
    async with async_session() as session:
        record = await session.get(YourModel, thing_id)
        if not record:
            return {"error": f"Thing #{thing_id} not found"}

        # Mark as processing
        record.status = YourStatus.PROCESSING.value
        await session.commit()

        # Capture fields needed outside the session
        record_name = record.name
        record_project = record.project_name

    logger.info(f"Processing thing #{thing_id}: {record_name}")

    if ctx:
        await ctx.report_progress(progress=0, total=100)
        await ctx.info(f"Processing thing #{thing_id}: {record_name}")

    try:
        # Step 1: Do work
        result_data = await do_expensive_operation(record_name)

        if ctx:
            await ctx.report_progress(progress=50, total=100)

        # Step 2: Store results
        async with async_session() as session:
            # ... store results ...
            pass

        # Step 3: Mark as completed
        async with async_session() as session:
            rec = await session.get(YourModel, thing_id)
            if rec:
                rec.status = YourStatus.COMPLETED.value
                await session.commit()

        if ctx:
            await ctx.report_progress(progress=100, total=100)
            await ctx.info(f"Thing #{thing_id} completed")

        return {"thing_id": thing_id, "status": "completed"}

    except Exception as e:
        logger.error(f"Thing #{thing_id} failed: {e}")

        async with async_session() as session:
            rec = await session.get(YourModel, thing_id)
            if rec:
                rec.status = YourStatus.FAILED.value
                rec.error_message = str(e)[:2000]
                await session.commit()

        if ctx:
            await ctx.error(f"Thing #{thing_id} failed: {e}")

        return {"thing_id": thing_id, "status": "failed", "error": str(e)}
```

### The Status Tool (polling)

```python
@tool(tags={"your_domain", "read"}, annotations={"readOnlyHint": True})
async def get_thing_status(
    thing_id: int,
    ctx: Context | None = None,
) -> dict:
    """Check the status of a background thing.

    Args:
        thing_id: The ID returned by start_thing.
    """
    async_session = get_async_session_factory()
    async with async_session() as session:
        record = await session.get(YourModel, thing_id)
        if not record:
            return {"error": f"Thing #{thing_id} not found"}

    result = {
        "thing_id": record.id,
        "name": record.name,
        "status": record.status,
        "project_name": record.project_name,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }

    if record.error_message:
        result["error_message"] = record.error_message

    return result
```

## Conventions

### Status Enum

Always define as `str, enum.Enum` with these standard states:

```python
class YourStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### Progress Reporting

Report at meaningful milestones, not every iteration:

```python
await ctx.report_progress(progress=0, total=100)    # Start
await ctx.report_progress(progress=20, total=100)   # After parsing
await ctx.report_progress(progress=50, total=100)   # After main work
await ctx.report_progress(progress=80, total=100)   # After storage
await ctx.report_progress(progress=100, total=100)  # Complete
```

### Error Handling

- Wrap the entire task body in `try/except Exception`
- Store error message truncated to 2000 chars: `str(e)[:2000]`
- Always update status to `FAILED` on error
- Log via `logger.error()` AND `ctx.error()` (they serve different audiences)
- Return `{"status": "failed", "error": str(e)}` — never raise

### Parallel Operations Within Tasks

Use `asyncio.gather()` for independent operations:

```python
import asyncio

tasks = [expensive_op(item) for item in items]
results = await asyncio.gather(*tasks)
```

### Session Discipline

- Capture fields you need *before* leaving the session context
- Open new sessions for each independent DB operation
- Don't hold sessions open across `await` calls to external APIs

## Registration

Register all three tools (trigger, task, status) in `server.py`:

```python
from solomons_library.tools.your_module import start_thing, process_thing, get_thing_status

for t in [
    # ... existing tools ...
    start_thing, process_thing, get_thing_status,
]:
    mcp.add_tool(t)
```

## See Also

- `solomon-mcp-tool` — For the general tool pattern (non-background)
- `solomon-model-migration` — For creating the status-tracking model
