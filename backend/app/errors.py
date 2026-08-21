"""Structured application errors (see DESIGN.md §28)."""

from __future__ import annotations


class FabricError(Exception):
    """A domain error that maps cleanly onto a structured API response."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


# Convenience factories for the failure modes enumerated in the design.
def invalid_selection(message: str) -> FabricError:
    return FabricError("INVALID_SELECTION", message, 422)


def selection_too_large(message: str) -> FabricError:
    return FabricError("SELECTION_TOO_LARGE", message, 422)


def empty_geometry(message: str) -> FabricError:
    return FabricError("EMPTY_GEOMETRY", message, 404)


def provider_error(message: str) -> FabricError:
    return FabricError("PROVIDER_ERROR", message, 502)


def geometry_error(message: str) -> FabricError:
    return FabricError("GEOMETRY_ERROR", message, 500)
