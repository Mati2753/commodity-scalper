"""Session token container (repr never exposes values)."""

from dataclasses import dataclass


@dataclass(slots=True, repr=False)
class SessionTokens:
    cst: str
    security_token: str
    account_id: str | None = None

    def __repr__(self) -> str:
        return (
            "SessionTokens(cst='[REDACTED]', security_token='[REDACTED]', "
            f"account_id={self.account_id!r})"
        )
