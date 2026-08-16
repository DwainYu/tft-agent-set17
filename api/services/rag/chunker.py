"""Document chunking for RAG ingestion.

This module is the *document parsing* stage of the RAG pipeline.  It turns
raw, potentially long documents into retrieval-ready chunks, each carrying
rich provenance metadata (source file, heading path, chunk index) so that
downstream answers can cite exactly where a fact came from.

Two complementary splitters are provided:

* :class:`RecursiveCharacterSplitter` — a general-purpose, language-agnostic
  splitter.  It recursively breaks text using a hierarchy of separators
  (paragraph -> line -> sentence -> word -> char), keeping each chunk under
  ``chunk_size`` while re-including ``chunk_overlap`` characters of context
  between adjacent chunks so sentences are not orphaned at a boundary.

* :class:`MarkdownSplitter` — heading-aware.  It walks a Markdown document's
  heading hierarchy, chunks *within* each section, and prefixes every chunk
  with its heading path (e.g. ``装备推荐 > 主C装备``) so each chunk is
  self-contained even when read in isolation.

Both emit :class:`Chunk` objects rather than bare strings, which is what makes
attribution/citation possible later on.

Design notes
------------
* Chunking is deliberately **pure** (no I/O, no model calls) so it is trivially
  unit-testable and cheap to run over a whole corpus.
* ``chunk_size`` / ``chunk_overlap`` are tuned for Chinese TFT guide text; they
  are configurable per the "measure before you optimize" principle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Chunk data class
# ---------------------------------------------------------------------------


@dataclass
class Chunk:
    """A single retrieval-ready piece of a document.

    Attributes
    ----------
    content:
        The text that will be embedded and returned on retrieval.  For
        Markdown chunks this is prefixed with the heading path so the chunk is
        self-contained.
    metadata:
        Provenance used for filtering and citation, e.g. ``source``,
        ``title``, ``heading_path``, ``chunk_index``, ``doc_type``.
    """

    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


# ---------------------------------------------------------------------------
# Recursive character splitter
# ---------------------------------------------------------------------------

#: Default separator hierarchy: paragraph, line, CJK sentence end, Latin
#: sentence end, word boundary, then raw characters as a last resort.
DEFAULT_SEPARATORS: list[str] = [
    "\n\n",  # paragraph
    "\n",    # line
    "。",    # CJK full stop
    "！",
    "？",
    "；",
    ". ",    # Latin full stop (keep trailing space to avoid gluing words)
    "! ",
    "? ",
    " ",     # word
    "",      # character
]


class RecursiveCharacterSplitter:
    """Recursively split text into overlapping chunks under ``chunk_size``.

    The algorithm picks the *coarsest* separator that actually appears in the
    text, splits on it, and greedily merges the pieces back up to
    ``chunk_size``.  Any piece still too large is re-split with the next,
    finer separator.  Adjacent chunks share up to ``chunk_overlap`` characters
    so that a fact straddling a boundary is still retrievable.
    """

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 80,
        separators: list[str] | None = None,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or list(DEFAULT_SEPARATORS)

    # -- public API ---------------------------------------------------------

    def split(self, text: str) -> list[str]:
        """Split *text* into a list of chunk strings (never empty strings)."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        chunks = self._split(text, self.separators)
        return [c for c in chunks if c.strip()]

    # -- internals ----------------------------------------------------------

    def _split(self, text: str, separators: list[str]) -> list[str]:
        # Choose the coarsest separator present in the text.
        separator = separators[-1]
        remaining: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "" or sep in text:
                separator = sep
                remaining = separators[i + 1 :]
                break

        pieces = text.split(separator) if separator else list(text)

        chunks: list[str] = []
        buffer: list[str] = []
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) <= self.chunk_size:
                buffer.append(piece)
            else:
                # Flush what we have, then break the oversized piece further.
                if buffer:
                    chunks.extend(self._merge(buffer, separator))
                    buffer = []
                if remaining:
                    chunks.extend(self._split(piece, remaining))
                else:
                    chunks.append(piece)  # cannot split any finer
        if buffer:
            chunks.extend(self._merge(buffer, separator))
        return chunks

    def _merge(self, pieces: list[str], separator: str) -> list[str]:
        """Greedily pack *pieces* into chunks <= chunk_size with overlap."""
        joiner = separator if separator.strip() != "" or separator == "" else separator
        # For non-whitespace separators (e.g. '。') we keep them when re-joining
        # so sentences don't lose their terminators.
        keep_sep = separator not in (" ", "\n", "\n\n")

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for piece in pieces:
            piece_len = len(piece) + (len(separator) if current else 0)
            if current and current_len + piece_len > self.chunk_size:
                chunks.append(self._join(current, separator, keep_sep))
                # Start the next chunk with the tail of the previous one so the
                # overlap window of context is preserved.
                current = self._tail_for_overlap(current, separator)
                current_len = sum(len(p) for p in current)
            current.append(piece)
            current_len += piece_len

        if current:
            chunks.append(self._join(current, separator, keep_sep))
        return chunks

    @staticmethod
    def _join(pieces: list[str], separator: str, keep_sep: bool) -> str:
        if keep_sep:
            return "".join(p + separator for p in pieces[:-1]) + pieces[-1]
        return separator.join(pieces)

    def _tail_for_overlap(self, pieces: list[str], separator: str) -> list[str]:
        """Return the trailing pieces whose total length fits the overlap."""
        tail: list[str] = []
        acc = 0
        for piece in reversed(pieces):
            if acc + len(piece) > self.chunk_overlap:
                break
            tail.insert(0, piece)
            acc += len(piece)
        return tail


# ---------------------------------------------------------------------------
# Markdown (heading-aware) splitter
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class MarkdownSplitter:
    """Heading-aware chunker for Markdown documents.

    Every chunk is scoped to a section and carries the full heading path, so a
    chunk about ``主C装备`` is still meaningful when retrieved on its own.
    Section bodies are split with an internal :class:`RecursiveCharacterSplitter`.
    """

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 80,
        include_heading_in_content: bool = True,
    ) -> None:
        self._inner = RecursiveCharacterSplitter(chunk_size, chunk_overlap)
        self.include_heading_in_content = include_heading_in_content

    # -- public API ---------------------------------------------------------

    def split(
        self,
        text: str,
        *,
        source: str = "",
        base_metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk a Markdown *text* and return provenance-tagged :class:`Chunk` s."""
        title = self.extract_title(text)
        sections = self._parse_sections(text)
        chunks: list[Chunk] = []
        index = 0
        for heading_path, body in sections:
            heading_ctx = " > ".join(heading_path)
            for piece in self._inner.split(body):
                if self.include_heading_in_content and heading_ctx:
                    content = f"[{heading_ctx}] {piece}"
                else:
                    content = piece
                metadata = dict(base_metadata or {})
                metadata.update(
                    {
                        "source": source,
                        "title": title,
                        "heading_path": heading_ctx,
                        "chunk_index": index,
                    }
                )
                chunks.append(Chunk(content=content, metadata=metadata))
                index += 1
        return chunks

    def split_file(self, path: Path | str, base_metadata: dict | None = None) -> list[Chunk]:
        """Read and chunk a single Markdown file."""
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        meta = dict(base_metadata or {})
        meta.setdefault("source", path.name)
        return self.split(text, source=meta["source"], base_metadata=meta)

    def split_directory(
        self,
        directory: Path | str,
        pattern: str = "*.md",
        base_metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk every file matching *pattern* under *directory* (recursive)."""
        directory = Path(directory)
        all_chunks: list[Chunk] = []
        for path in sorted(directory.rglob(pattern)):
            if path.is_file():
                all_chunks.extend(self.split_file(path, base_metadata))
        return all_chunks

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def extract_title(text: str) -> str:
        """Return the first H1 title, or an empty string if none."""
        m = _TITLE_RE.search(text)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _parse_sections(text: str) -> list[tuple[list[str], str]]:
        """Walk headings and group body text under each heading path.

        Returns a list of ``(heading_path, body)`` tuples in document order.
        Content before the first heading uses an empty heading path.
        """
        sections: list[tuple[list[str], str]] = []
        stack: list[tuple[int, str]] = []  # (level, title)
        current_path: list[str] = []
        current_body: list[str] = []

        def flush() -> None:
            body = "\n".join(current_body).strip()
            if body:
                sections.append((list(current_path), body))

        for line in text.split("\n"):
            m = _HEADING_RE.match(line)
            if m:
                flush()
                current_body = []
                level = len(m.group(1))
                title = m.group(2).strip()
                if level == 1:
                    # H1 is the document title: it is tracked separately in
                    # metadata, so reset the section stack and keep it out of
                    # the heading path to avoid redundant prefixes.
                    stack = []
                    current_path = []
                    continue
                # Pop back to the parent level, then push this heading.
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                current_path = [t for _, t in stack]
            else:
                current_body.append(line)
        flush()
        return sections
