from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from flipradar.services import notification_service
from flipradar.services.email_service import EmailSendResult


@pytest.mark.asyncio
async def test_watchlist_transition_creates_all_typed_notifications(monkeypatch):
    created: list[dict] = []

    async def list_preferences(*_args):
        return {
            "price_drop": SimpleNamespace(in_app_enabled=True, email_enabled=True),
        }

    async def create_notification(_db, data):
        created.append(data)
        return SimpleNamespace(**data)

    monkeypatch.setattr(
        notification_service.repositories,
        "list_notification_preferences",
        list_preferences,
    )
    monkeypatch.setattr(
        notification_service.repositories, "create_notification", create_notification
    )
    previous = SimpleNamespace(
        id=uuid4(),
        listing_price=Decimal("120"),
        target_price=Decimal("100"),
        listing_status="active",
        deal_score=Decimal("55"),
    )
    current = SimpleNamespace(
        id=uuid4(),
        listing_price=Decimal("90"),
        target_price=Decimal("100"),
        listing_status="ended",
        deal_score=Decimal("75"),
    )
    item = SimpleNamespace(
        id=uuid4(), lego_set=SimpleNamespace(set_number="10316-1"), listing=None
    )

    notifications = await notification_service.emit_watchlist_notifications(
        object(),
        user_id=uuid4(),
        item=item,
        previous=previous,
        current=current,
        material_price_change_percent=Decimal("10"),
    )

    assert len(notifications) == 4
    assert {entry["notification_type"] for entry in created} == {
        "price_drop",
        "target_reached",
        "ended_listing",
        "deal_score",
    }
    price_drop = next(
        entry for entry in created if entry["notification_type"] == "price_drop"
    )
    assert price_drop["email_eligible"] is True
    assert price_drop["drop_percent"] == Decimal("25.00")


@pytest.mark.asyncio
async def test_email_digest_batches_pending_notifications_per_user(monkeypatch):
    user = SimpleNamespace(id=uuid4(), username="owner", email="owner@example.com")
    pending = [
        SimpleNamespace(id=uuid4(), title="Price drop", message="Now $90"),
        SimpleNamespace(id=uuid4(), title="Target reached", message="At target"),
    ]
    sent_ids: list = []
    email_calls: list[dict] = []

    class FakeEmailService:
        async def send(self, **kwargs):
            email_calls.append(kwargs)
            return EmailSendResult(attempted=True, sent=True)

    async def users_with_pending(_db):
        return [user]

    async def pending_for_user(_db, user_id):
        assert user_id == user.id
        return pending

    async def mark_sent(_db, notification_ids, *, sent_at):
        assert sent_at is not None
        sent_ids.extend(notification_ids)

    monkeypatch.setattr(
        notification_service.repositories,
        "list_users_with_pending_notification_emails",
        users_with_pending,
    )
    monkeypatch.setattr(
        notification_service.repositories,
        "list_pending_notification_emails",
        pending_for_user,
    )
    monkeypatch.setattr(
        notification_service.repositories, "mark_notification_emails_sent", mark_sent
    )
    monkeypatch.setattr(
        notification_service, "get_email_service", lambda: FakeEmailService()
    )

    result = await notification_service.deliver_pending_email_digests(object())

    assert result == {"users": 1, "pending": 2, "delivered": 2}
    assert len(email_calls) == 1
    assert "Price drop" in email_calls[0]["text_body"]
    assert sent_ids == [notification.id for notification in pending]
