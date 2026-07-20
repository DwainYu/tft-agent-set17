import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterable, Optional


@dataclass
class SSEEvent:
    """A single Server-Sent Event payload."""

    stage: str
    content: Optional[str] = None
    data: Optional[dict] = field(default=None)

    def encode(self) -> bytes:
        """Serialize the event into an SSE wire-format byte string."""
        payload: dict = {"stage": self.stage}
        if self.content is not None:
            payload["content"] = self.content
        if self.data is not None:
            payload["data"] = self.data
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


async def sse_stream(events: Iterable[SSEEvent]) -> AsyncIterator[bytes]:
    """Async generator that yields encoded SSE bytes for each event."""
    for event in events:
        yield event.encode()
