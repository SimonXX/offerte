"""Stato su SQLite: canali, offerte, post, regole scattate, notifiche, redirect risolti."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    name TEXT PRIMARY KEY,
    last_id INTEGER NOT NULL DEFAULT 0,
    bootstrapped INTEGER NOT NULL DEFAULT 0,
    last_fetch TEXT,
    last_status TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    title TEXT,
    text TEXT NOT NULL,
    link TEXT,
    permalink TEXT NOT NULL,
    image TEXT,
    price REAL,
    old_price REAL,
    discount INTEGER,
    coupon TEXT,
    posted_at TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    channels TEXT NOT NULL,
    n_posts INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS offers_key ON offers(key, first_seen);
CREATE INDEX IF NOT EXISTS offers_posted ON offers(posted_at);
CREATE TABLE IF NOT EXISTS posts (
    channel TEXT NOT NULL,
    msg_id INTEGER NOT NULL,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    posted_at TEXT NOT NULL,
    permalink TEXT NOT NULL,
    PRIMARY KEY (channel, msg_id)
);
CREATE INDEX IF NOT EXISTS posts_offer ON posts(offer_id);
CREATE TABLE IF NOT EXISTS matches (
    rule TEXT NOT NULL,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    matched_at TEXT NOT NULL,
    PRIMARY KEY (rule, offer_id)
);
CREATE TABLE IF NOT EXISTS notifications (
    offer_id INTEGER PRIMARY KEY REFERENCES offers(id),
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS redirects (
    url TEXT PRIMARY KEY,
    resolved TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);
"""


@dataclass
class Offer:
    id: int
    key: str
    title: str | None
    text: str
    link: str | None
    permalink: str
    image: str | None
    price: float | None
    old_price: float | None
    discount: int | None
    coupon: str | None
    posted_at: str
    first_seen: str
    last_seen: str
    channels: list[str]
    n_posts: int


def _offer(row: sqlite3.Row) -> Offer:
    d = dict(row)
    d["channels"] = json.loads(d["channels"])
    return Offer(**d)


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- canali -------------------------------------------------------------

    def channel_state(self, name: str) -> tuple[int, bool]:
        row = self.db.execute("SELECT last_id, bootstrapped FROM channels WHERE name = ?", (name,)).fetchone()
        return (row["last_id"], bool(row["bootstrapped"])) if row else (0, False)

    def update_channel(self, name: str, *, status: str, now: str, error: str | None = None,
                       last_id: int | None = None, bootstrapped: bool | None = None) -> None:
        self.db.execute("INSERT OR IGNORE INTO channels(name) VALUES (?)", (name,))
        self.db.execute("UPDATE channels SET last_fetch = ?, last_status = ?, last_error = ? WHERE name = ?",
                        (now, status, error, name))
        if last_id is not None:
            self.db.execute("UPDATE channels SET last_id = max(last_id, ?) WHERE name = ?", (last_id, name))
        if bootstrapped is not None:
            self.db.execute("UPDATE channels SET bootstrapped = ? WHERE name = ?", (int(bootstrapped), name))
        self.db.commit()

    # --- post e offerte -------------------------------------------------------

    def post_exists(self, channel: str, msg_id: int) -> bool:
        return self.db.execute("SELECT 1 FROM posts WHERE channel = ? AND msg_id = ?", (channel, msg_id)).fetchone() is not None

    def add_post(self, channel: str, msg_id: int, offer_id: int, posted_at: str, permalink: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO posts(channel, msg_id, offer_id, posted_at, permalink) VALUES (?,?,?,?,?)",
                        (channel, msg_id, offer_id, posted_at, permalink))
        self.db.commit()

    def find_offer(self, key: str, since: str) -> Offer | None:
        row = self.db.execute("SELECT * FROM offers WHERE key = ? AND first_seen >= ? ORDER BY first_seen DESC LIMIT 1",
                              (key, since)).fetchone()
        return _offer(row) if row else None

    def get_offer(self, offer_id: int) -> Offer:
        return _offer(self.db.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone())

    def insert_offer(self, *, key: str, title: str | None, text: str, link: str | None, permalink: str,
                     image: str | None, price: float | None, old_price: float | None, discount: int | None,
                     coupon: str | None, posted_at: str, channel: str, now: str) -> int:
        cur = self.db.execute(
            "INSERT INTO offers(key, title, text, link, permalink, image, price, old_price, discount, coupon,"
            " posted_at, first_seen, last_seen, channels) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, title, text, link, permalink, image, price, old_price, discount, coupon,
             posted_at, now, now, json.dumps([channel])))
        self.db.commit()
        return int(cur.lastrowid)

    def touch_offer(self, offer_id: int, channel: str, now: str) -> None:
        """Stessa offerta vista di nuovo: aggiunge il canale alla provenienza e aggiorna last_seen."""
        channels = json.loads(self.db.execute("SELECT channels FROM offers WHERE id = ?", (offer_id,)).fetchone()[0])
        if channel not in channels:
            channels.append(channel)
        self.db.execute("UPDATE offers SET channels = ?, last_seen = ?, n_posts = n_posts + 1 WHERE id = ?",
                        (json.dumps(channels), now, offer_id))
        self.db.commit()

    def offers_for_channels(self, channels: list[str], since: str, limit: int) -> list[Offer]:
        if not channels:
            return []
        marks = ",".join("?" * len(channels))
        rows = self.db.execute(
            f"SELECT o.* FROM offers o WHERE o.posted_at >= ? AND EXISTS"
            f" (SELECT 1 FROM posts p WHERE p.offer_id = o.id AND p.channel IN ({marks}))"
            f" ORDER BY o.posted_at DESC LIMIT ?", (since, *channels, limit)).fetchall()
        return [_offer(r) for r in rows]

    def offers_for_rule(self, rule: str, since: str, limit: int) -> list[Offer]:
        rows = self.db.execute(
            "SELECT o.* FROM offers o JOIN matches m ON m.offer_id = o.id"
            " WHERE m.rule = ? AND o.posted_at >= ? ORDER BY o.posted_at DESC LIMIT ?", (rule, since, limit)).fetchall()
        return [_offer(r) for r in rows]

    def offers_since(self, since: str) -> list[Offer]:
        rows = self.db.execute("SELECT * FROM offers WHERE posted_at >= ? ORDER BY posted_at DESC", (since,)).fetchall()
        return [_offer(r) for r in rows]

    def unmatched_offers(self, rule: str, since: str) -> list[Offer]:
        rows = self.db.execute(
            "SELECT o.* FROM offers o WHERE o.first_seen >= ? AND NOT EXISTS"
            " (SELECT 1 FROM matches m WHERE m.rule = ? AND m.offer_id = o.id) ORDER BY o.id", (since, rule)).fetchall()
        return [_offer(r) for r in rows]

    # --- regole e notifiche ---------------------------------------------------

    def add_match(self, rule: str, offer_id: int, now: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO matches(rule, offer_id, matched_at) VALUES (?,?,?)", (rule, offer_id, now))
        self.db.commit()

    def is_notified(self, offer_id: int) -> bool:
        return self.db.execute("SELECT 1 FROM notifications WHERE offer_id = ?", (offer_id,)).fetchone() is not None

    def mark_notified(self, offer_id: int, now: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO notifications(offer_id, sent_at) VALUES (?,?)", (offer_id, now))
        self.db.commit()

    # --- redirect -------------------------------------------------------------

    def get_redirect(self, url: str) -> str | None:
        row = self.db.execute("SELECT resolved FROM redirects WHERE url = ?", (url,)).fetchone()
        return row[0] if row else None

    def set_redirect(self, url: str, resolved: str, now: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO redirects(url, resolved, resolved_at) VALUES (?,?,?)", (url, resolved, now))
        self.db.commit()

    # --- ricerca e statistiche ------------------------------------------------

    def search(self, term: str, limit: int) -> list[Offer]:
        t = term.lower()
        rows = self.db.execute(
            "SELECT * FROM offers WHERE instr(lower(text), ?) > 0 OR instr(lower(coalesce(title, '')), ?) > 0"
            " ORDER BY posted_at DESC LIMIT ?", (t, t, limit)).fetchall()
        return [_offer(r) for r in rows]

    def posts_per_day(self, since: str) -> list[tuple[str, str, int]]:
        rows = self.db.execute(
            "SELECT channel, date(posted_at, 'localtime') AS day, count(*) AS n FROM posts"
            " WHERE posted_at >= ? GROUP BY channel, day ORDER BY channel, day", (since,)).fetchall()
        return [(r["channel"], r["day"], r["n"]) for r in rows]

    def rules_fired(self, since: str) -> list[tuple[str, int, str]]:
        rows = self.db.execute(
            "SELECT rule, count(*) AS n, max(matched_at) AS last FROM matches WHERE matched_at >= ?"
            " GROUP BY rule ORDER BY n DESC", (since,)).fetchall()
        return [(r["rule"], r["n"], r["last"]) for r in rows]

    def counts(self) -> dict[str, int]:
        return {t: self.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("offers", "posts", "channels")}
