"""Schéma initial du chatbot éducatif.

Crée les tables : users, conversations, messages, faqs, knowledge_entries, usage_stats.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column("language_preference", sa.String(5), nullable=False, server_default="fr"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("total_messages", sa.Integer, server_default="0"),
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200)),
        sa.Column("language", sa.String(5), nullable=False, server_default="fr"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="fr"),
        sa.Column("translated_content", sa.Text),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("intent", sa.String(50)),
        sa.Column("confidence", sa.Float),
        sa.Column("source", sa.String(20), server_default="llm"),
        sa.Column("response_time_ms", sa.Integer),
    )
    op.create_index("ix_messages_conv_timestamp", "messages", ["conversation_id", "timestamp"])

    # --- faqs ---
    op.create_table(
        "faqs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="fr", index=True),
        sa.Column("embedding", sa.Text),
        sa.Column("tags", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), index=True),
        sa.Column("view_count", sa.Integer, server_default="0"),
    )

    # --- knowledge_entries ---
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="fr"),
        sa.Column("tags", sa.Text),
        sa.Column("embedding", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
    )

    # --- usage_stats ---
    op.create_table(
        "usage_stats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("total_messages", sa.Integer, server_default="0"),
        sa.Column("faq_hits", sa.Integer, server_default="0"),
        sa.Column("llm_calls", sa.Integer, server_default="0"),
        sa.Column("language_fr", sa.Integer, server_default="0"),
        sa.Column("language_wo", sa.Integer, server_default="0"),
        sa.Column("language_ff", sa.Integer, server_default="0"),
        sa.Column("language_ar", sa.Integer, server_default="0"),
        sa.Column("avg_response_time_ms", sa.Float, server_default="0.0"),
        sa.Column("unique_sessions", sa.Integer, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("usage_stats")
    op.drop_table("knowledge_entries")
    op.drop_index("ix_messages_conv_timestamp", table_name="messages")
    op.drop_table("faqs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
