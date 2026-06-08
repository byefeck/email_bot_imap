"""add chat destination, make mailbox fields nullable

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("dest_chat_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("dest_thread_id", sa.Integer(), nullable=True))
        # "Сбросить почту" обнуляет эти поля, не удаляя саму строку User
        # (в ней же хранится привязка чата) — поэтому им нужно стать nullable.
        batch_op.alter_column("imap_host", existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column("imap_port", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column("encrypted_secret", existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("encrypted_secret", existing_type=sa.LargeBinary(), nullable=False)
        batch_op.alter_column("email", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("imap_port", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("imap_host", existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column("dest_thread_id")
        batch_op.drop_column("dest_chat_id")
