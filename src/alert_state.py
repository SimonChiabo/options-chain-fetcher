"""
src/alert_state.py
Gate de cooldown edge-triggered. Evita el spam de notificar la misma condicion
en cada ciclo de polling. Una condicion dispara al activarse; mientras siga
activa se re-notifica como mucho una vez cada min_interval segundos (medido
desde el ultimo disparo). Una clave despejada se olvida cuando pasa min_interval
desde su ultimo disparo, de modo que una reactivacion posterior cuenta como un
flanco nuevo.
"""

from datetime import datetime
from typing import Optional

from src.rules import Alert


class AlertState:
    def __init__(self, min_interval: float = 300.0) -> None:
        self.min_interval = min_interval
        self._last_fired: dict[tuple[str, str], datetime] = {}

    def update(self, current: list[Alert], now: Optional[datetime] = None) -> list[Alert]:
        """
        Recibe las alertas activas de este ciclo y devuelve solo las que se
        deben notificar (nuevas, o re-disparadas tras min_interval).
        """
        now = now or datetime.now()
        current_keys = {(a.rule_name, a.subject) for a in current}

        to_notify: list[Alert] = []
        for alert in current:
            key = (alert.rule_name, alert.subject)
            last = self._last_fired.get(key)
            if last is None or (now - last).total_seconds() >= self.min_interval:
                to_notify.append(alert)
                self._last_fired[key] = now

        # Re-armar: olvidar claves que llevan despejadas al menos min_interval.
        for key in list(self._last_fired):
            if key not in current_keys:
                if (now - self._last_fired[key]).total_seconds() >= self.min_interval:
                    del self._last_fired[key]

        return to_notify
