from dataclasses import dataclass
from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ModelTier(StrEnum):
    """Model selection policy (doc 03 NFR-4): fast tier for low-stakes steps,
    quality tier for design/reasoning. Mapped to concrete model ids in config."""

    QUALITY = "quality"
    FAST = "fast"


@dataclass(frozen=True)
class LLMMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class TokenUsage:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class RawCompletion:
    text: str
    usage: TokenUsage
