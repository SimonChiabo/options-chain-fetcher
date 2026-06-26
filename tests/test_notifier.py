"""Tests para src/notifier.py. requests y toast mockeados, sin red."""

from datetime import datetime

import pytest

from src.notifier import (
    TelegramNotifier, DesktopNotifier, CompositeNotifier, format_message,
)
from src.rules import Alert


def _alert() -> Alert:
    return Alert(
        rule_name="high_iv", symbol="SPY", scope="contract", subject="SPY 100C",
        field="iv", value=0.42, threshold=0.3, timestamp=datetime(2026, 6, 26, 10, 0),
        message="IV alta en SPY 100C",
    )


class _FakeResponse:
    ok = True


class _FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, timeout=None):
        self.calls.append({"url": url, "data": data})
        return _FakeResponse()


def test_format_message_includes_subject_and_value():
    msg = format_message(_alert())
    assert "SPY 100C" in msg
    assert "0.42" in msg


def test_telegram_posts_to_bot_api():
    session = _FakeSession()
    notifier = TelegramNotifier(token="TKN", chat_id="123", session=session)
    notifier.send(_alert())
    assert len(session.calls) == 1
    assert "/botTKN/sendMessage" in session.calls[0]["url"]
    assert session.calls[0]["data"]["chat_id"] == "123"
    assert "SPY 100C" in session.calls[0]["data"]["text"]


def test_telegram_swallows_network_error():
    class _BoomSession:
        def post(self, *a, **k):
            raise RuntimeError("network down")

    notifier = TelegramNotifier(token="TKN", chat_id="123", session=_BoomSession())
    # Must not raise.
    notifier.send(_alert())


def test_desktop_uses_injected_toast_fn():
    captured = {}

    def fake_toast(title, body):
        captured["title"] = title
        captured["body"] = body

    notifier = DesktopNotifier(toast_fn=fake_toast)
    notifier.send(_alert())
    assert "SPY 100C" in captured["body"]


def test_composite_continues_after_failing_notifier():
    sent = []

    class _Boom:
        def send(self, alert):
            raise RuntimeError("boom")

    class _Record:
        def send(self, alert):
            sent.append(alert)

    composite = CompositeNotifier([_Boom(), _Record()])
    composite.send(_alert())
    assert len(sent) == 1
