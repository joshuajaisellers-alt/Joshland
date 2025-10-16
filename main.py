"""Command-line interface for the Correspondence Tracker."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable

from correspondence_tracker.database import Database
from correspondence_tracker.services import TrackerService, default_database_path

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Datetime must be in ISO format YYYY-MM-DDTHH:MM:SS"
        ) from exc


def comma_separated(value: str) -> Iterable[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone Correspondence Tracker")
    parser.add_argument(
        "--db",
        type=Path,
        default=default_database_path(),
        help="Path to the SQLite database file (default: ~/.correspondence_tracker/tracker.db)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # Contacts -----------------------------------------------------------------
    add_contact = sub.add_parser("add-contact", help="Create a new contact")
    add_contact.add_argument("name")
    add_contact.add_argument("--email")
    add_contact.add_argument("--phone")
    add_contact.add_argument("--preferred-channel")
    add_contact.add_argument("--notes")

    sub.add_parser("list-contacts", help="List all contacts")

    # Correspondence -----------------------------------------------------------
    add_corr = sub.add_parser("log", help="Log an incoming or outgoing message")
    add_corr.add_argument("contact_id", type=int)
    add_corr.add_argument("direction", choices=["incoming", "outgoing"])
    add_corr.add_argument(
        "sent_at",
        type=parse_datetime,
        help="ISO timestamp of when the message was sent",
    )
    add_corr.add_argument("--medium")
    add_corr.add_argument("--subject")
    add_corr.add_argument("--body")
    add_corr.add_argument("--attachment")
    add_corr.add_argument("--sentiment")
    add_corr.add_argument("--tags", type=comma_separated)
    add_corr.add_argument("--topic")
    add_corr.add_argument("--follow-up", type=parse_datetime)
    add_corr.add_argument("--status")

    list_corr = sub.add_parser("history", help="Show correspondence history")
    list_corr.add_argument("--contact-id", type=int)

    # Reminders & insights -----------------------------------------------------
    pending = sub.add_parser("reminders", help="Show pending follow-ups")
    pending.add_argument(
        "--overdue-only",
        action="store_true",
        help="Only show follow-ups that are past their due date",
    )

    insights = sub.add_parser("insights", help="Summarize a relationship")
    insights.add_argument("contact_id", type=int)

    sub.add_parser("active", help="List active correspondents from last 30 days")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    db = Database(args.db)
    service = TrackerService(db)

    if args.command == "add-contact":
        contact_id = service.add_contact(
            args.name,
            email=args.email,
            phone=args.phone,
            preferred_channel=getattr(args, "preferred_channel", None),
            notes=args.notes,
        )
        print(f"Contact created with id {contact_id}")

    elif args.command == "list-contacts":
        contacts = service.list_contacts()
        for c in contacts:
            preferred = f" | preferred: {c.preferred_channel}" if c.preferred_channel else ""
            print(f"[{c.id}] {c.name}{preferred}")
            if c.email:
                print(f"    email: {c.email}")
            if c.phone:
                print(f"    phone: {c.phone}")
            if c.notes:
                print(f"    notes: {c.notes}")

    elif args.command == "log":
        contact_id = getattr(args, "contact_id")
        sent_at = getattr(args, "sent_at")
        correspondence_id = service.add_correspondence(
            contact_id=contact_id,
            direction=args.direction,
            sent_at=sent_at,
            medium=args.medium,
            subject=args.subject,
            body=args.body,
            attachment_path=args.attachment,
            sentiment=args.sentiment,
            tags=args.tags,
            related_topic=args.topic,
            follow_up_date=args.follow_up,
            response_status=args.status,
        )
        print(f"Correspondence logged with id {correspondence_id}")

    elif args.command == "history":
        correspondences = service.list_correspondences(getattr(args, "contact_id", None))
        for item in correspondences:
            sent = item.sent_at.strftime(ISO_FORMAT)
            follow_up = item.follow_up_date.strftime(ISO_FORMAT) if item.follow_up_date else "-"
            print(
                f"[{item.id}] contact={item.contact_id} {item.direction} {sent}"
                f" medium={item.medium or '-'} status={item.response_status or '-'} follow_up={follow_up}"
            )
            if item.subject:
                print(f"    subject: {item.subject}")
            if item.tags:
                print(f"    tags: {item.tags}")
            if item.related_topic:
                print(f"    topic: {item.related_topic}")
            if item.sentiment:
                print(f"    sentiment: {item.sentiment}")
            if item.body:
                print(f"    body: {item.body[:200]}{'...' if len(item.body) > 200 else ''}")
            if item.attachment_path:
                print(f"    attachment: {item.attachment_path}")

    elif args.command == "reminders":
        reminders = service.reminder_summary()
        now = datetime.utcnow()
        for contact, corr, due in reminders:
            overdue = due < now
            if args.overdue_only and not overdue:
                continue
            status = "OVERDUE" if overdue else "due"
            print(
                f"{status} {due.strftime(ISO_FORMAT)} -> contact {contact.name}"
                f" (correspondence #{corr.id}, subject={corr.subject or '-'})"
            )

    elif args.command == "insights":
        summary = service.basic_insights(args.contact_id)
        for key, value in summary.items():
            if isinstance(value, datetime):
                value = value.strftime(ISO_FORMAT)
            print(f"{key}: {value}")

    elif args.command == "active":
        active = service.active_contacts()
        if not active:
            print("No active correspondents in the selected window.")
        for contact in active:
            print(f"[{contact.id}] {contact.name}")

    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
