"""Entity matcher – scans free-text for known champion / item / trait / augment names."""
from __future__ import annotations

import re
import sqlite3

# Characters to strip for generating name variants (middle dots, spaces, hyphens, apostrophes)
_STRIP_CHARS = re.compile(r"[·\s\-'']")


def _name_variants(name: str) -> list[str]:
    """Return the original name plus a stripped variant for fuzzy matching."""
    stripped = _STRIP_CHARS.sub("", name)
    if stripped and stripped != name:
        return [name, stripped]
    return [name]


class EntityMatcher:
    """Load alias and name mappings once, then match entities in arbitrary text.

    Supports: champion (via aliases table + name_zh/name_en),
              item, trait, augment (via name_zh/name_en).
    Matching strategy: longest-first, case-insensitive, de-duplicated.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # key (lowercased) -> {"type", "canonical_id", "name_zh", "name_en", "cost"}
        self._lookup: dict[str, dict] = {}
        self._load_champions()
        self._load_items()
        self._load_traits()
        self._load_augments()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_champions(self) -> None:
        """Load champions from aliases table + name_zh / name_en."""
        # Aliases table first (higher priority for nicknames / short forms)
        cur = self._conn.execute(
            "SELECT a.alias, c.id, c.name_zh, c.name_en, c.cost "
            "FROM aliases a JOIN champions c ON a.champion_id = c.id"
        )
        for row in cur.fetchall():
            alias, champ_id, name_zh, name_en, cost = row
            key = alias.lower().strip()
            if key:
                self._lookup[key] = {
                    "type": "champion",
                    "canonical_id": champ_id,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "cost": cost,
                }

        # Also add champion name_zh and name_en as aliases
        cur2 = self._conn.execute(
            "SELECT id, name_zh, name_en, cost FROM champions"
        )
        for champ_id, name_zh, name_en, cost in cur2.fetchall():
            for name in (name_zh, name_en):
                if name:
                    for variant in _name_variants(name):
                        key = variant.lower().strip()
                        if key and key not in self._lookup:
                            self._lookup[key] = {
                                "type": "champion",
                                "canonical_id": champ_id,
                                "name_zh": name_zh,
                                "name_en": name_en,
                                "cost": cost,
                            }

    def _load_items(self) -> None:
        cur = self._conn.execute("SELECT id, name_zh, name_en FROM items")
        for item_id, name_zh, name_en in cur.fetchall():
            # Skip items with empty Chinese name (e.g. EmptyBag)
            if not name_zh:
                continue
            for name in (name_zh, name_en):
                if name:
                    key = name.lower().strip()
                    if key and key not in self._lookup:
                        self._lookup[key] = {
                            "type": "item",
                            "canonical_id": item_id,
                            "name_zh": name_zh,
                            "name_en": name_en or "",
                            "cost": None,
                        }

    def _load_traits(self) -> None:
        cur = self._conn.execute("SELECT id, name_zh, name_en FROM traits")
        for trait_id, name_zh, name_en in cur.fetchall():
            if not name_zh:
                continue
            for name in (name_zh, name_en):
                if name:
                    key = name.lower().strip()
                    if key and key not in self._lookup:
                        self._lookup[key] = {
                            "type": "trait",
                            "canonical_id": trait_id,
                            "name_zh": name_zh,
                            "name_en": name_en or "",
                            "cost": None,
                        }

    def _load_augments(self) -> None:
        cur = self._conn.execute("SELECT id, name_zh, name_en FROM augments")
        for aug_id, name_zh, name_en in cur.fetchall():
            if not name_zh:
                continue
            for name in (name_zh, name_en):
                if name:
                    key = name.lower().strip()
                    if key and key not in self._lookup:
                        self._lookup[key] = {
                            "type": "augment",
                            "canonical_id": aug_id,
                            "name_zh": name_zh,
                            "name_en": name_en or "",
                            "cost": None,
                        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, text: str) -> list[dict]:
        """Scan *text* for all known entities, longest-first, de-duplicated.

        Returns a list of dicts::

            {"type": "champion", "canonical_id": "TFT17_Jinx",
             "name_zh": "金克丝", "name_en": "Jinx", "cost": 2}
        """
        text_lower = text.lower()
        seen: set[str] = set()
        results: list[dict] = []

        # Sort lookup keys longest-first so longer matches take priority
        for alias in sorted(self._lookup, key=len, reverse=True):
            if alias in text_lower:
                entity = self._lookup[alias]
                dedup_key = f"{entity['type']}:{entity['canonical_id']}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    results.append(dict(entity))  # shallow copy

        return results
