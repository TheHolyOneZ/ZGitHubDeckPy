# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    etag       TEXT,
    fetched_at REAL NOT NULL,
    hits       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS responses_fetched_at ON responses (fetched_at);
"""


@dataclass(slots=True)
class CacheEntry:
    key: str
    value: Any
    etag: str | None
    fetched_at: float

    @property
    def age(self) -> float:
        return max(time.time() - self.fetched_at, 0.0)

    def fresh_for(self, ttl: float) -> bool:
        return self.age < ttl


@dataclass(slots=True)
class CacheStats:
    entries: int = 0
    bytes: int = 0
    oldest: float | None = None
    newest: float | None = None
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class CacheManager:

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self._connection = self._connect()


    def _connect(self) -> sqlite3.Connection:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, check_same_thread=False)
        except (OSError, sqlite3.Error):
            connection = sqlite3.connect(":memory:", check_same_thread=False)

        connection.executescript(
            "PRAGMA journal_mode=WAL;\nPRAGMA synchronous=NORMAL;\n" + SCHEMA
        )
        connection.commit()
        return connection

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.commit()
                self._connection.close()
            except sqlite3.Error:
                pass


    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT payload, etag, fetched_at FROM responses WHERE key = ?",
                    (key,),
                ).fetchone()
            except sqlite3.Error:
                return None

        if row is None:
            self.misses += 1
            return None

        payload, etag, fetched_at = row
        try:
            value = json.loads(payload)
        except ValueError:
            self.misses += 1
            return None

        self.hits += 1
        return CacheEntry(key=key, value=value, etag=etag, fetched_at=float(fetched_at))

    def fresh(self, key: str, ttl: float) -> Any | None:
        entry = self.get(key)
        if entry is not None and entry.fresh_for(ttl):
            return entry.value
        return None

    def etag(self, key: str) -> str | None:
        entry = self.get(key)
        return entry.etag if entry else None

    def age(self, key: str) -> float | None:
        entry = self.get(key)
        return entry.age if entry else None


    def put(self, key: str, value: Any, etag: str | None = None) -> None:
        try:
            payload = json.dumps(value, separators=(",", ":"))
        except (TypeError, ValueError):
            return
        stamp = time.time()
        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO responses (key, payload, etag, fetched_at, hits)
                    VALUES (?, ?, ?, ?, 0)
                    ON CONFLICT(key) DO UPDATE SET
                        payload    = excluded.payload,
                        etag       = COALESCE(excluded.etag, responses.etag),
                        fetched_at = excluded.fetched_at,
                        hits       = responses.hits + 1
                    """,
                    (key, payload, etag, stamp),
                )
                self._connection.commit()
            except sqlite3.Error:
                pass

    def touch(self, key: str) -> None:
        with self._lock:
            try:
                self._connection.execute(
                    "UPDATE responses SET fetched_at = ?, hits = hits + 1 WHERE key = ?",
                    (time.time(), key),
                )
                self._connection.commit()
            except sqlite3.Error:
                pass


    def clear(self, prefix: str | None = None) -> int:
        with self._lock:
            try:
                if prefix:
                    cursor = self._connection.execute(
                        "DELETE FROM responses WHERE key LIKE ?", (f"{prefix}%",)
                    )
                else:
                    cursor = self._connection.execute("DELETE FROM responses")
                self._connection.commit()
                removed = cursor.rowcount or 0
            except sqlite3.Error:
                return 0
        self._vacuum()
        return removed

    def prune(self, older_than: float) -> int:
        cutoff = time.time() - older_than
        with self._lock:
            try:
                cursor = self._connection.execute(
                    "DELETE FROM responses WHERE fetched_at < ?", (cutoff,)
                )
                self._connection.commit()
                return cursor.rowcount or 0
            except sqlite3.Error:
                return 0

    def _vacuum(self) -> None:
        with self._lock:
            try:
                self._connection.execute("VACUUM")
            except sqlite3.Error:
                pass

    def stats(self) -> CacheStats:
        with self._lock:
            try:
                row = self._connection.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(LENGTH(payload)), 0),
                           MIN(fetched_at), MAX(fetched_at)
                    FROM responses
                    """
                ).fetchone()
            except sqlite3.Error:
                row = None

        if not row:
            return CacheStats(hits=self.hits, misses=self.misses)

        entries, size, oldest, newest = row
        return CacheStats(
            entries=int(entries or 0),
            bytes=int(size or 0),
            oldest=float(oldest) if oldest else None,
            newest=float(newest) if newest else None,
            hits=self.hits,
            misses=self.misses,
        )

    def describe(self) -> str:
        stats = self.stats()
        if not stats.entries:
            return "empty"
        size = stats.bytes
        if size < 1024:
            readable = f"{size} B"
        elif size < 1024 * 1024:
            readable = f"{size / 1024:.0f} KB"
        else:
            readable = f"{size / (1024 * 1024):.1f} MB"
        age = time.time() - stats.newest if stats.newest else 0
        if age < 90:
            freshness = "just now"
        elif age < 3600:
            freshness = f"{int(age // 60)}m ago"
        elif age < 86400:
            freshness = f"{int(age // 3600)}h ago"
        else:
            freshness = f"{int(age // 86400)}d ago"
        return f"{stats.entries} entries · {readable} · updated {freshness}"

















