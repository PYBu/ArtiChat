"""Merge the ArtiChat 0.1.7 and Open WebUI 0.11 migration branches.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7, f0bd01a18a3d
"""

from collections.abc import Sequence

revision: str = 'd3e4f5a6b7c8'
down_revision: tuple[str, str] = ('c2d3e4f5a6b7', 'f0bd01a18a3d')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both histories without changing application data."""


def downgrade() -> None:
    """Split the history back into its two parent heads."""
