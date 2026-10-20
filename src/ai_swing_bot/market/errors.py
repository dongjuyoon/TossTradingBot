"""Sanitized errors for external market services."""

from __future__ import annotations


class TossAPIError(RuntimeError):
    """An API failure that never embeds credentials or response bodies."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
