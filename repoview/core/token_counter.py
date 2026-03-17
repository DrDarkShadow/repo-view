"""Token counting utilities."""

try:
    import tiktoken
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    _tokenizer = None


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken or fallback estimation."""
    if _tokenizer:
        return len(_tokenizer.encode(text, disallowed_special=()))
    return len(text) // 3
