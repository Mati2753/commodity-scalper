"""Logging setup and defensive secret redaction."""

import logging
import re
from collections.abc import Iterable

SENSITIVE_KEYS = re.compile(r"(?i)(x-cap-api-key|x-security-token|cst|password|api[_-]?key)")


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self.secrets = tuple(value for value in secrets if value)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        message = re.sub(
            r"(?i)((?:cst|x-security-token|password|api[_-]?key)[\"'=:\s]+)[^,\s}\"]+",
            r"\1[REDACTED]",
            message,
        )
        record.msg, record.args = message, ()
        return True


def configure_logging(secrets: Iterable[str] = (), verbose: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter(secrets))
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
