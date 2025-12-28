from datetime import datetime, timedelta

import pytest

from correspondence_tracker.database import Database
from correspondence_tracker.services import TrackerService


@pytest.fixture
def service(tmp_path):
    db_path = tmp_path / "tracker.db"
    database = Database(db_path)
    tracker = TrackerService(database)
    yield tracker
    database.close()


def test_add_and_list_contact(service):
    contact_id = service.add_contact(
        "Alice",
        email="alice@example.com",
        phone="123",
        preferred_channel="email",
        notes="Met at conference",
    )

    contacts = service.list_contacts()

    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.id == contact_id
    assert contact.name == "Alice"
    assert contact.email == "alice@example.com"
    assert contact.preferred_channel == "email"
    assert contact.notes == "Met at conference"


def test_add_correspondence_defaults_pending(service):
    contact_id = service.add_contact("Bob")
    sent_at = datetime(2024, 1, 1, 10, 0, 0)
    follow_up = datetime(2024, 1, 15, 10, 0, 0)

    corr_id = service.add_correspondence(
        contact_id=contact_id,
        direction="outgoing",
        sent_at=sent_at,
        subject="Hello",
        body="Checking in",
        tags=["follow-up", "greeting"],
        follow_up_date=follow_up,
    )

    correspondences = service.list_correspondences(contact_id)

    assert len(correspondences) == 1
    correspondence = correspondences[0]
    assert correspondence.id == corr_id
    assert correspondence.response_status == "pending"
    assert correspondence.tags == "follow-up,greeting"
    assert correspondence.follow_up_date == follow_up


def test_reminder_summary_includes_pending(service):
    contact_id = service.add_contact("Carol")
    sent_at = datetime.utcnow() - timedelta(days=7)
    follow_up = datetime.utcnow() - timedelta(days=1)

    service.add_correspondence(
        contact_id=contact_id,
        direction="outgoing",
        sent_at=sent_at,
        follow_up_date=follow_up,
    )

    reminders = service.reminder_summary()

    assert len(reminders) == 1
    contact, correspondence, due_date = reminders[0]
    assert contact.id == contact_id
    assert correspondence.contact_id == contact_id
    assert abs((due_date - follow_up).total_seconds()) < 1


def test_basic_insights_returns_summary(service):
    contact_id = service.add_contact("Dana")
    first = datetime(2024, 1, 1, 10, 0, 0)
    second = datetime(2024, 1, 15, 9, 0, 0)

    service.add_correspondence(
        contact_id=contact_id,
        direction="outgoing",
        sent_at=second,
        sentiment="positive",
    )
    service.add_correspondence(
        contact_id=contact_id,
        direction="incoming",
        sent_at=first,
        sentiment="neutral",
    )

    summary = service.basic_insights(contact_id)

    assert summary["total_messages"] == 2
    assert summary["incoming"] == 1
    assert summary["outgoing"] == 1
    assert summary["latest_sentiment"] == "positive"
    assert summary["average_gap_days"] >= 0
