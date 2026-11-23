"""Point d'entree de l'API. Re-exporte l'application assemblee dans app.main."""

from app.main import app  # noqa: F401

__all__ = ["app"]
