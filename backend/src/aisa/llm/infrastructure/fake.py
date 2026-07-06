import json
import types
from collections.abc import Callable
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from aisa.llm.domain.messages import LLMMessage, ModelTier, RawCompletion, TokenUsage

Handler = Callable[[str, list[LLMMessage], type[BaseModel]], str]


def _default_for(annotation: object) -> object:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):  # Optional[...] -> None
        return None
    if origin in (list, set, tuple):
        return []
    if origin is dict:
        return {}
    if annotation is str:
        return ""
    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _minimal_dict(annotation)
    if get_args(annotation):
        return _default_for(get_args(annotation)[0])
    return None


def _minimal_dict(model: type[BaseModel]) -> dict[str, object]:
    """Smallest dict that validates against `model` (required fields only;
    optional fields fall back to their defaults)."""
    return {
        name: _default_for(field.annotation)
        for name, field in model.model_fields.items()
        if field.is_required()
    }


class FakeLLMProvider:
    """Deterministic provider for tests and key-less local dev.

    Three modes: a fixed queue of JSON strings, a handler computing the reply
    from the conversation, or (default) auto-generating a schema-valid minimal
    instance so the whole app runs without a key or network."""

    def __init__(
        self, *, responses: list[str] | None = None, handler: Handler | None = None
    ) -> None:
        if responses is not None and handler is not None:
            raise ValueError("provide at most one of responses or handler")
        self._responses = list(responses) if responses is not None else None
        self._handler = handler
        self.calls: list[tuple[str, list[LLMMessage]]] = []

    async def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_model: type[BaseModel],
        tier: ModelTier,
    ) -> RawCompletion:
        self.calls.append((system, list(messages)))
        if self._handler is not None:
            text = self._handler(system, messages, response_model)
        elif self._responses is not None:
            if not self._responses:
                raise AssertionError("FakeLLMProvider ran out of scripted responses")
            text = self._responses.pop(0)
        else:
            text = json.dumps(_minimal_dict(response_model))
        return RawCompletion(
            text=text, usage=TokenUsage(model="fake", input_tokens=10, output_tokens=20)
        )
