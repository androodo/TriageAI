"""Initial migration — create all tables and pgvector extension

Revision ID: 001_initial
Revises:
Create Date: 2025-01-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create ci_runs table
    op.create_table(
        "ci_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_name", sa.String(255), nullable=False),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("pipeline_id", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("passed", "failed", "skipped", name="ci_status", create_constraint=True),
            nullable=False,
        ),
        sa.Column("test_suite_name", sa.String(255), nullable=False),
        sa.Column("failed_test_names", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ci_runs_repo_name", "ci_runs", ["repo_name"])
    op.create_index("ix_ci_runs_branch", "ci_runs", ["branch"])
    op.create_index("ix_ci_runs_environment", "ci_runs", ["environment"])
    op.create_index("ix_ci_runs_status", "ci_runs", ["status"])

    # Create failure_logs table
    op.create_table(
        "failure_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ci_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ci_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("raw_log_text", sa.Text(), nullable=False),
        sa.Column("cleaned_log_text", sa.Text(), nullable=False),
        sa.Column("extracted_errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("stack_traces", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("exception_names", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("failed_tests", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("timeout_indicators", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dependency_errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("infrastructure_errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_failure_logs_ci_run_id", "failure_logs", ["ci_run_id"])

    # Create triage_results table
    op.create_table(
        "triage_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ci_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ci_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "failure_category",
            postgresql.ENUM(
                "test_assertion_failure",
                "application_code_bug",
                "flaky_test",
                "dependency_configuration_issue",
                "infrastructure_environment_failure",
                "timeout_performance_issue",
                "unknown",
                name="failure_category",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("owner_guess", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("suggested_steps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("issue_title", sa.String(500), nullable=False),
        sa.Column("issue_body", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_triage_results_ci_run_id", "triage_results", ["ci_run_id"])

    # Create issue_drafts table
    op.create_table(
        "issue_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ci_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ci_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("labels", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("assignee_guess", sa.String(255), nullable=True),
        sa.Column(
            "format",
            postgresql.ENUM("github", "jira", name="issue_format", create_constraint=True),
            nullable=False,
            server_default="github",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_issue_drafts_ci_run_id", "issue_drafts", ["ci_run_id"])

    # Create HNSW index on embeddings for fast similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_failure_logs_embedding_cosine
        ON failure_logs
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.drop_table("issue_drafts")
    op.drop_table("triage_results")
    op.drop_table("failure_logs")
    op.drop_table("ci_runs")
    op.execute("DROP TYPE IF EXISTS issue_format")
    op.execute("DROP TYPE IF EXISTS failure_category")
    op.execute("DROP TYPE IF EXISTS ci_status")
    op.execute("DROP EXTENSION IF EXISTS vector")