from fastmcp.prompts import Message, prompt


@prompt(tags={"analysis"})
def analyze_book(title: str, author: str) -> list[Message]:
    """Generate a prompt for literary analysis of a specific book."""
    return [
        Message(
            f"Please provide a detailed literary analysis of '{title}' by {author}. "
            f"Cover the following aspects:\n"
            f"1. Major themes and motifs\n"
            f"2. Writing style and narrative structure\n"
            f"3. Historical and cultural context\n"
            f"4. Character development\n"
            f"5. Critical reception and legacy"
        ),
    ]


@prompt(tags={"search"})
def search_query(topic: str, depth: str = "brief") -> str:
    """Generate a prompt for searching the knowledge base on a topic."""
    if depth == "detailed":
        return (
            f"Search the knowledge base thoroughly for information about '{topic}'. "
            f"Provide comprehensive results including all related embeddings, "
            f"cross-references between sources, and a synthesis of findings."
        )
    return f"Search the knowledge base for key information about '{topic}' and provide a concise summary."


@prompt(tags={"analysis"})
def summarize_collection() -> list[Message]:
    """Generate a prompt to summarize the entire library collection."""
    return [
        Message(
            "Please summarize the contents of Solomon's Library. "
            "List the books by category, highlight key themes across the collection, "
            "and identify any notable gaps in coverage."
        ),
        Message(
            "I'll analyze the library collection systematically.",
            role="assistant",
        ),
    ]


ALL_PROMPTS = [analyze_book, search_query, summarize_collection]
