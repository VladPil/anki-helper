"""Initial migration with all tables for AnkiRAG.

Revision ID: 001_initial
Revises:
Create Date: 2025-01-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types
    op.execute("""
        CREATE TYPE prompt_category AS ENUM (
            'generation', 'fact_check', 'chat', 'improvement'
        )
    """)
    op.execute("""
        CREATE TYPE cardstatus AS ENUM (
            'draft', 'approved', 'rejected', 'synced'
        )
    """)

    # =====================
    # LLM Models table
    # =====================
    op.create_table(
        "llm_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_functions", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("input_price_per_million", sa.Float(), nullable=True),
        sa.Column("output_price_per_million", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("extra_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_models")),
        sa.UniqueConstraint("name", name=op.f("uq_llm_models_name")),
    )
    op.create_index(op.f("ix_llm_models_name"), "llm_models", ["name"], unique=False)
    op.create_index(op.f("ix_llm_models_provider"), "llm_models", ["provider"], unique=False)
    op.create_index(op.f("ix_llm_models_is_active"), "llm_models", ["is_active"], unique=False)

    # =====================
    # Embedding Models table
    # =====================
    op.create_table(
        "embedding_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column(
            "supported_languages",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY['en']::varchar[]"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_models")),
        sa.UniqueConstraint("name", name=op.f("uq_embedding_models_name")),
    )
    op.create_index(op.f("ix_embedding_models_name"), "embedding_models", ["name"], unique=False)
    op.create_index(
        op.f("ix_embedding_models_provider"), "embedding_models", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_embedding_models_is_active"), "embedding_models", ["is_active"], unique=False
    )

    # =====================
    # Users table
    # =====================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_deleted_at"), "users", ["deleted_at"], unique=False)

    # =====================
    # User Preferences table
    # =====================
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="ru"),
        sa.Column("default_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_embedder_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["default_model_id"],
            ["llm_models.id"],
            name=op.f("fk_user_preferences_default_model_id_llm_models"),
        ),
        sa.ForeignKeyConstraint(
            ["default_embedder_id"],
            ["embedding_models.id"],
            name=op.f("fk_user_preferences_default_embedder_id_embedding_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_preferences_user_id")),
    )

    # =====================
    # Refresh Tokens table
    # =====================
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token", name=op.f("uq_refresh_tokens_token")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=False)

    # =====================
    # Decks table
    # =====================
    op.create_table(
        "decks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anki_deck_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_decks_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["decks.id"],
            name=op.f("fk_decks_parent_id_decks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decks")),
    )
    op.create_index(op.f("ix_decks_owner_id"), "decks", ["owner_id"], unique=False)
    op.create_index(op.f("ix_decks_parent_id"), "decks", ["parent_id"], unique=False)
    op.create_index("ix_decks_owner_parent", "decks", ["owner_id", "parent_id"], unique=False)
    op.create_index(op.f("ix_decks_deleted_at"), "decks", ["deleted_at"], unique=False)

    # =====================
    # Card Templates table
    # =====================
    op.create_table(
        "card_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("fields_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("front_template", sa.Text(), nullable=False),
        sa.Column("back_template", sa.Text(), nullable=False),
        sa.Column("css", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_card_templates_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_templates")),
    )
    op.create_index(op.f("ix_card_templates_name"), "card_templates", ["name"], unique=False)
    op.create_index(op.f("ix_card_templates_owner_id"), "card_templates", ["owner_id"], unique=False)

    # =====================
    # Template Fields table
    # =====================
    op.create_table(
        "template_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["card_templates.id"],
            name=op.f("fk_template_fields_template_id_card_templates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_template_fields")),
    )
    op.create_index(
        op.f("ix_template_fields_template_id"), "template_fields", ["template_id"], unique=False
    )

    # =====================
    # Prompts table
    # =====================
    op.create_table(
        "prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(
                "generation", "fact_check", "chat", "improvement",
                name="prompt_category",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("variables_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preferred_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["preferred_model_id"],
            ["llm_models.id"],
            name=op.f("fk_prompts_preferred_model_id_llm_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["prompts.id"],
            name=op.f("fk_prompts_parent_id_prompts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompts")),
        sa.UniqueConstraint("name", name=op.f("uq_prompts_name")),
    )
    op.create_index(op.f("ix_prompts_name"), "prompts", ["name"], unique=False)
    op.create_index(op.f("ix_prompts_category"), "prompts", ["category"], unique=False)
    op.create_index(op.f("ix_prompts_is_active"), "prompts", ["is_active"], unique=False)
    op.create_index(op.f("ix_prompts_parent_id"), "prompts", ["parent_id"], unique=False)
    op.create_index(
        op.f("ix_prompts_preferred_model_id"), "prompts", ["preferred_model_id"], unique=False
    )

    # =====================
    # Prompt Executions table
    # =====================
    op.create_table(
        "prompt_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rendered_system_prompt", sa.Text(), nullable=False),
        sa.Column("rendered_user_prompt", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["prompts.id"],
            name=op.f("fk_prompt_executions_prompt_id_prompts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_prompt_executions_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["llm_models.id"],
            name=op.f("fk_prompt_executions_model_id_llm_models"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_executions")),
    )
    op.create_index(
        op.f("ix_prompt_executions_prompt_id"), "prompt_executions", ["prompt_id"], unique=False
    )
    op.create_index(
        op.f("ix_prompt_executions_user_id"), "prompt_executions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_prompt_executions_trace_id"), "prompt_executions", ["trace_id"], unique=False
    )

    # =====================
    # Cards table
    # =====================
    op.create_table(
        "cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "approved", "rejected", "synced",
                name="cardstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("anki_card_id", sa.BigInteger(), nullable=True),
        sa.Column("anki_note_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["deck_id"],
            ["decks.id"],
            name=op.f("fk_cards_deck_id_decks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["card_templates.id"],
            name=op.f("fk_cards_template_id_card_templates"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cards")),
    )
    op.create_index(op.f("ix_cards_deck_id"), "cards", ["deck_id"], unique=False)
    op.create_index(op.f("ix_cards_status"), "cards", ["status"], unique=False)
    op.create_index("ix_cards_deck_status", "cards", ["deck_id", "status"], unique=False)
    op.create_index(op.f("ix_cards_deleted_at"), "cards", ["deleted_at"], unique=False)

    # =====================
    # Card Generation Info table
    # =====================
    op.create_table(
        "card_generation_info",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("fact_check_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fact_check_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
            name=op.f("fk_card_generation_info_card_id_cards"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["prompts.id"],
            name=op.f("fk_card_generation_info_prompt_id_prompts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["llm_models.id"],
            name=op.f("fk_card_generation_info_model_id_llm_models"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_generation_info")),
        sa.UniqueConstraint("card_id", name=op.f("uq_card_generation_info_card_id")),
    )

    # =====================
    # Card Embeddings table (with pgvector)
    # =====================
    op.create_table(
        "card_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
            name=op.f("fk_card_embeddings_card_id_cards"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["embedder_id"],
            ["embedding_models.id"],
            name=op.f("fk_card_embeddings_embedder_id_embedding_models"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_embeddings")),
        sa.UniqueConstraint("card_id", name=op.f("uq_card_embeddings_card_id")),
    )

    # Add vector column using raw SQL (pgvector)
    op.execute("""
        ALTER TABLE card_embeddings
        ADD COLUMN embedding vector(1536)
    """)

    # Create IVFFlat index for vector similarity search
    op.execute("""
        CREATE INDEX ix_card_embeddings_vector
        ON card_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # =====================
    # Chat Sessions table
    # =====================
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_sessions")),
    )
    op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False)

    # =====================
    # Chat Messages table
    # =====================
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name=op.f("fk_chat_messages_session_id_chat_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False
    )

    # =====================
    # Insert default data
    # =====================

    # Insert default LLM models
    op.execute("""
        INSERT INTO llm_models (id, name, display_name, provider, model_id,
                               max_tokens, supports_vision, supports_functions)
        VALUES
            ('01234567-89ab-cdef-0123-456789abcde0', 'gpt-4o', 'GPT-4o',
             'openai', 'gpt-4o', 128000, true, true),
            ('01234567-89ab-cdef-0123-456789abcde1', 'gpt-4o-mini', 'GPT-4o Mini',
             'openai', 'gpt-4o-mini', 128000, true, true),
            ('01234567-89ab-cdef-0123-456789abcde2', 'claude-3-5-sonnet', 'Claude 3.5 Sonnet',
             'anthropic', 'claude-3-5-sonnet-20241022', 200000, true, true)
    """)

    # Insert default embedding models
    op.execute("""
        INSERT INTO embedding_models (id, name, display_name, provider, model_id,
                                     dimension, supported_languages)
        VALUES
            ('01234567-89ab-cdef-0123-456789abcdf0', 'text-embedding-3-small',
             'OpenAI Embedding Small', 'openai', 'text-embedding-3-small',
             1536, ARRAY['en', 'ru']),
            ('01234567-89ab-cdef-0123-456789abcdf1', 'text-embedding-3-large',
             'OpenAI Embedding Large', 'openai', 'text-embedding-3-large',
             3072, ARRAY['en', 'ru'])
    """)

    # Insert default card templates
    op.execute("""
        INSERT INTO card_templates (id, name, display_name, fields_schema,
                                   front_template, back_template, css, is_system)
        VALUES
            ('01234567-89ab-cdef-0123-456789abce00', 'basic', 'Basic',
             '{"type": "object", "properties": {"Front": {"type": "string"}, "Back": {"type": "string"}}, "required": ["Front", "Back"]}',
             '{{Front}}',
             '{{FrontSide}}<hr id="answer">{{Back}}',
             '.card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }',
             true),
            ('01234567-89ab-cdef-0123-456789abce01', 'basic-reversed', 'Basic (and reversed card)',
             '{"type": "object", "properties": {"Front": {"type": "string"}, "Back": {"type": "string"}}, "required": ["Front", "Back"]}',
             '{{Front}}',
             '{{FrontSide}}<hr id="answer">{{Back}}',
             '.card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }',
             true),
            ('01234567-89ab-cdef-0123-456789abce02', 'cloze', 'Cloze',
             '{"type": "object", "properties": {"Text": {"type": "string"}, "Extra": {"type": "string"}}, "required": ["Text"]}',
             '{{cloze:Text}}',
             '{{cloze:Text}}<br>{{Extra}}',
             '.card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; } .cloze { font-weight: bold; color: blue; }',
             true)
    """)

    # Insert template fields for basic template
    op.execute("""
        INSERT INTO template_fields (id, template_id, name, field_type, is_required, "order")
        VALUES
            ('01234567-89ab-cdef-0123-456789abcf00', '01234567-89ab-cdef-0123-456789abce00',
             'Front', 'text', true, 0),
            ('01234567-89ab-cdef-0123-456789abcf01', '01234567-89ab-cdef-0123-456789abce00',
             'Back', 'text', true, 1),
            ('01234567-89ab-cdef-0123-456789abcf02', '01234567-89ab-cdef-0123-456789abce01',
             'Front', 'text', true, 0),
            ('01234567-89ab-cdef-0123-456789abcf03', '01234567-89ab-cdef-0123-456789abce01',
             'Back', 'text', true, 1),
            ('01234567-89ab-cdef-0123-456789abcf04', '01234567-89ab-cdef-0123-456789abce02',
             'Text', 'text', true, 0),
            ('01234567-89ab-cdef-0123-456789abcf05', '01234567-89ab-cdef-0123-456789abce02',
             'Extra', 'text', false, 1)
    """)

    # Insert default prompts
    op.execute("""
        INSERT INTO prompts (id, name, description, category, system_prompt,
                            user_prompt_template, variables_schema, is_active)
        VALUES
            ('01234567-89ab-cdef-0123-456789abd000', 'card_generation_basic',
             'Generate basic flashcards from text',
             'generation',
             'You are an expert at creating effective flashcards for learning. Create clear, concise flashcards that test one concept at a time. Each card should have a clear question/prompt on the front and a complete answer on the back.',
             'Create {{count}} flashcards about the following topic:\n\n{{topic}}\n\nFormat each card as:\nFront: [question or prompt]\nBack: [answer or explanation]',
             '{"type": "object", "properties": {"topic": {"type": "string", "description": "The topic to create flashcards about"}, "count": {"type": "integer", "description": "Number of cards to generate", "default": 5}}, "required": ["topic"]}',
             true),
            ('01234567-89ab-cdef-0123-456789abd001', 'fact_check',
             'Verify factual accuracy of generated content',
             'fact_check',
             'You are a fact-checking expert. Analyze the given flashcard content for factual accuracy. Identify any errors, misconceptions, or potentially misleading information.',
             'Please fact-check the following flashcard:\n\nFront: {{front}}\nBack: {{back}}\n\nProvide:\n1. Accuracy assessment (accurate/partially accurate/inaccurate)\n2. Confidence score (0-100)\n3. Any corrections needed\n4. Sources if available',
             '{"type": "object", "properties": {"front": {"type": "string"}, "back": {"type": "string"}}, "required": ["front", "back"]}',
             true),
            ('01234567-89ab-cdef-0123-456789abd002', 'chat_assistant',
             'General chat assistant for learning help',
             'chat',
             'You are a helpful learning assistant. Help users understand concepts, answer questions, and provide guidance for their studies. Be encouraging and thorough in your explanations.',
             '{{message}}',
             '{"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}',
             true)
    """)


def downgrade() -> None:
    """Drop all tables."""
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_index("ix_card_embeddings_vector", table_name="card_embeddings")
    op.drop_table("card_embeddings")
    op.drop_table("card_generation_info")
    op.drop_table("cards")
    op.drop_table("prompt_executions")
    op.drop_table("prompts")
    op.drop_table("template_fields")
    op.drop_table("card_templates")
    op.drop_table("decks")
    op.drop_table("refresh_tokens")
    op.drop_table("user_preferences")
    op.drop_table("users")
    op.drop_table("embedding_models")
    op.drop_table("llm_models")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS cardstatus")
    op.execute("DROP TYPE IF EXISTS prompt_category")

    # Drop pgvector extension (optional - may affect other databases)
    # op.execute("DROP EXTENSION IF EXISTS vector")
