"""Domain services for managing contacts and correspondences."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from .database import Database

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


@dataclass
class Contact:
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    preferred_channel: Optional[str]
    notes: Optional[str]


@dataclass
class Correspondence:
    id: int
    contact_id: int
    direction: str
    medium: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    attachment_path: Optional[str]
    sentiment: Optional[str]
    tags: Optional[str]
    related_topic: Optional[str]
    sent_at: datetime
    follow_up_date: Optional[datetime]
    response_status: Optional[str]


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class TrackerService:
    """High-level API for working with tracker data."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # Contacts -----------------------------------------------------------------
    def add_contact(
        self,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        preferred_channel: str | None = None,
        notes: str | None = None,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO contacts (name, email, phone, preferred_channel, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, phone, preferred_channel, notes),
        )
        return int(cur.lastrowid)

    def list_contacts(self) -> list[Contact]:
        rows = self.db.query(
            "SELECT id, name, email, phone, preferred_channel, notes FROM contacts ORDER BY name"
        )
        return [
            Contact(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                preferred_channel=row["preferred_channel"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def get_contact(self, contact_id: int) -> Optional[Contact]:
        rows = self.db.query(
            "SELECT id, name, email, phone, preferred_channel, notes FROM contacts WHERE id = ?",
            (contact_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return Contact(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            preferred_channel=row["preferred_channel"],
            notes=row["notes"],
        )

    # Correspondence -----------------------------------------------------------
    def add_correspondence(
        self,
        contact_id: int,
        direction: str,
        sent_at: datetime,
        medium: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        attachment_path: str | None = None,
        sentiment: str | None = None,
        tags: Iterable[str] | None = None,
        related_topic: str | None = None,
        follow_up_date: datetime | None = None,
        response_status: str | None = None,
    ) -> int:
        tags_str = ",".join(tags) if tags else None
        cur = self.db.execute(
            """
            INSERT INTO correspondences (
                contact_id, direction, medium, subject, body, attachment_path,
                sentiment, tags, related_topic, sent_at, follow_up_date, response_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_id,
                direction,
                medium,
                subject,
                body,
                attachment_path,
                sentiment,
                tags_str,
                related_topic,
                sent_at.strftime(ISO_FORMAT),
                follow_up_date.strftime(ISO_FORMAT) if follow_up_date else None,
                response_status or "pending",
            ),
        )
        return int(cur.lastrowid)

    def list_correspondences(self, contact_id: Optional[int] = None) -> list[Correspondence]:
        if contact_id is None:
            rows = self.db.query(
                "SELECT * FROM correspondences ORDER BY datetime(sent_at) DESC"
            )
        else:
            rows = self.db.query(
                "SELECT * FROM correspondences WHERE contact_id = ? ORDER BY datetime(sent_at) DESC",
                (contact_id,),
            )
        return [
            Correspondence(
                id=row["id"],
                contact_id=row["contact_id"],
                direction=row["direction"],
                medium=row["medium"],
                subject=row["subject"],
                body=row["body"],
                attachment_path=row["attachment_path"],
                sentiment=row["sentiment"],
                tags=row["tags"],
                related_topic=row["related_topic"],
                sent_at=datetime.fromisoformat(row["sent_at"]),
                follow_up_date=_parse_datetime(row["follow_up_date"]),
                response_status=row["response_status"],
            )
            for row in rows
        ]

    def update_response_status(self, correspondence_id: int, status: str) -> None:
        self.db.execute(
            "UPDATE correspondences SET response_status = ? WHERE id = ?",
            (status, correspondence_id),
        )

    # Heuristics ---------------------------------------------------------------
    def active_contacts(self, within_days: int = 30) -> list[Contact]:
        cutoff = datetime.utcnow() - timedelta(days=within_days)
        rows = self.db.query(
            """
            SELECT DISTINCT c.id, c.name, c.email, c.phone, c.preferred_channel, c.notes
            FROM contacts c
            JOIN correspondences co ON c.id = co.contact_id
            WHERE datetime(co.sent_at) >= datetime(?)
            ORDER BY c.name
            """,
            (cutoff.strftime(ISO_FORMAT),),
        )
        return [
            Contact(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                preferred_channel=row["preferred_channel"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def pending_follow_ups(self) -> list[Correspondence]:
        now_iso = datetime.utcnow().strftime(ISO_FORMAT)
        rows = self.db.query(
            """
            SELECT * FROM correspondences
            WHERE response_status = 'pending'
              AND follow_up_date IS NOT NULL
              AND datetime(follow_up_date) <= datetime(?)
            ORDER BY datetime(follow_up_date)
            """,
            (now_iso,),
        )
        return [
            Correspondence(
                id=row["id"],
                contact_id=row["contact_id"],
                direction=row["direction"],
                medium=row["medium"],
                subject=row["subject"],
                body=row["body"],
                attachment_path=row["attachment_path"],
                sentiment=row["sentiment"],
                tags=row["tags"],
                related_topic=row["related_topic"],
                sent_at=datetime.fromisoformat(row["sent_at"]),
                follow_up_date=_parse_datetime(row["follow_up_date"]),
                response_status=row["response_status"],
            )
            for row in rows
        ]

    def suggest_follow_up_date(self, last_interaction: datetime) -> datetime:
        """Suggest a follow-up based on recent cadence (simple heuristic)."""
        return last_interaction + timedelta(days=14)

    def reminder_summary(self) -> list[tuple[Contact, Correspondence, datetime]]:
        reminders = []
        pending = self.pending_follow_ups()
        for item in pending:
            contact = self.get_contact(item.contact_id)
            if contact is None:
                continue
            due = item.follow_up_date or datetime.utcnow()
            reminders.append((contact, item, due))
        return reminders

    def basic_insights(self, contact_id: int) -> dict[str, object]:
        corr = self.list_correspondences(contact_id)
        if not corr:
            return {"message": "No correspondence recorded yet."}

        total = len(corr)
        last_interaction = corr[0].sent_at
        incoming = sum(1 for c in corr if c.direction == "incoming")
        outgoing = total - incoming
        sentiments = [c.sentiment for c in corr if c.sentiment]
        latest_sentiment = sentiments[0] if sentiments else None

        average_gap = _average_gap_days(corr)

        return {
            "total_messages": total,
            "incoming": incoming,
            "outgoing": outgoing,
            "last_interaction": last_interaction,
            "latest_sentiment": latest_sentiment,
            "average_gap_days": average_gap,
            "suggested_follow_up": self.suggest_follow_up_date(last_interaction),
        }


def _average_gap_days(items: list[Correspondence]) -> Optional[float]:
    if len(items) < 2:
        return None
    gaps = []
    for first, second in zip(items, items[1:]):
        gaps.append((first.sent_at - second.sent_at).total_seconds() / 86400)
    return round(sum(gaps) / len(gaps), 2)


def default_database_path() -> Path:
    return Path.home() / ".correspondence_tracker" / "tracker.db"


__all__ = [
    "TrackerService",
    "Contact",
    "Correspondence",
    "default_database_path",
]
