from ulid import ULID


def new_id() -> str:
    """26-char Crockford ULID — time-sortable, no coordination required."""
    return str(ULID())
