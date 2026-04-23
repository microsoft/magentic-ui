"""Real-time alerting for stuck or failed runs.

See :mod:`.types` for the ``Alert`` dataclass, :mod:`.dispatcher` for the
multi-channel dispatcher, and :mod:`.channels` for concrete channels.
"""

from .dispatcher import AlertDispatcher
from .types import Alert, AlertChannel, AlertReason

__all__ = [
    "Alert",
    "AlertChannel",
    "AlertDispatcher",
    "AlertReason",
]
