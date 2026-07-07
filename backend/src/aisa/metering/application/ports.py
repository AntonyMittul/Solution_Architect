from datetime import datetime
from typing import Protocol


class UsageStore(Protocol):
    async def tokens_since(self, workspace_id: str, since: datetime) -> tuple[int, int]:
        """Returns (input_tokens, output_tokens) summed since `since`."""
        ...
