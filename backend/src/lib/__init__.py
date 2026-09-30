"""Cross-cutting helpers — standard library only.

Wires the JSON logger to the correlation-id context here so neither module has to import
the other: both stay import-free of ``src.*`` (AC-23 checks that with ``ast``).
"""

from src.lib import correlation, logging

logging.set_correlation_provider(correlation.get_correlation_id)

__all__ = ["correlation", "logging"]
