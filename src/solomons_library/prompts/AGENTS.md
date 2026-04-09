<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-10 | Updated: 2026-04-10 -->

# prompts

## Purpose
MCP prompt templates that generate structured messages for common library operations. Prompts guide AI assistants in performing literary analysis, knowledge base searches, and collection summaries.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | All prompt definitions and `ALL_PROMPTS` list for registration in `server.py` |

## For AI Agents

### Working In This Directory
- Prompts use `@prompt(tags={...})` decorator from `fastmcp.prompts`
- Prompts return either `str`, `list[Message]`, or `Message` objects
- New prompts must be added to the `ALL_PROMPTS` list
- Prompts are registered in `server.py` via `mcp.add_prompt(fn)`

### Available Prompts

| Name | Parameters | Description |
|------|------------|-------------|
| `analyze_book` | `title`, `author` | Literary analysis covering themes, style, context, characters, reception |
| `search_query` | `topic`, `depth="brief"` | Knowledge base search — brief or detailed mode |
| `summarize_collection` | (none) | Full library collection summary with gap analysis |

### Common Patterns
```python
@prompt(tags={"category"})
def my_prompt(param: str) -> list[Message]:
    return [Message(f"Instruction text with {param}")]
```

## Dependencies

### External
- `fastmcp` — `@prompt` decorator, `Message` class

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
