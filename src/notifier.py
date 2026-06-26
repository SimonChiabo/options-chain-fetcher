"""
src/notifier.py
Notificadores pluggables. Backends: toast de Windows y Telegram.
Un fallo de un canal nunca tumba a los demas. Nunca se loguea el token.
"""

import logging
from typing import Callable, Optional, Protocol

import requests

import config
from src.rules import Alert

log = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


def format_message(alert: Alert) -> str:
    """Texto humano de una alerta."""
    return (
        f"[{alert.symbol}] {alert.message}\n"
        f"{alert.field}={alert.value:g} (umbral {alert.threshold})"
    )


class Notifier(Protocol):
    def send(self, alert: Alert) -> None: ...


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, session: Optional[object] = None) -> None:
        self._token = token
        self._chat_id = chat_id
        self._session = session or requests.Session()

    def send(self, alert: Alert) -> None:
        url = f"{_TELEGRAM_API}/bot{self._token}/sendMessage"
        try:
            self._session.post(
                url,
                data={"chat_id": self._chat_id, "text": format_message(alert)},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 - canal aislado
            log.debug("Telegram send fallo: %s", exc)


def _show_windows_toast(title: str, body: str) -> None:
    from windows_toasts import Toast, WindowsToaster  # lazy import

    toaster = WindowsToaster("Options Alert Monitor")
    toast = Toast()
    toast.text_fields = [title, body]
    toaster.show_toast(toast)


class DesktopNotifier:
    def __init__(self, toast_fn: Optional[Callable[[str, str], None]] = None) -> None:
        self._toast_fn = toast_fn or _show_windows_toast

    def send(self, alert: Alert) -> None:
        try:
            self._toast_fn(f"Alerta {alert.symbol}", format_message(alert))
        except Exception as exc:  # noqa: BLE001 - toast no disponible
            log.debug("Desktop toast fallo: %s", exc)


class CompositeNotifier:
    def __init__(self, notifiers: list) -> None:
        self._notifiers = notifiers

    def send(self, alert: Alert) -> None:
        for notifier in self._notifiers:
            try:
                notifier.send(alert)
            except Exception as exc:  # noqa: BLE001 - canal aislado
                log.debug("Notificador fallo: %s", exc)


def build_notifier_from_config() -> CompositeNotifier:
    """Construye el CompositeNotifier segun los flags de config."""
    notifiers: list = []
    if config.ALERTS_DESKTOP:
        notifiers.append(DesktopNotifier())
    if config.ALERTS_TELEGRAM:
        notifiers.append(TelegramNotifier(
            token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID
        ))
    return CompositeNotifier(notifiers)
