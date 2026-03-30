"""Initial schema for TED F2 intelligence app."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260330_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("auth_provider", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "scan_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("STARTED", "COMPLETED", "FAILED", name="scanstatus", native_enum=False), nullable=False),
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        sa.Column("query_parameters", sa.JSON(), nullable=False),
        sa.Column("total_notices_returned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_notices_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_after_timing_filters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_high_fit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_conditional", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ignored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate_limit_events", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scan_runs_status"), "scan_runs", ["status"], unique=False)

    op.create_table(
        "notices",
        sa.Column("ted_notice_id", sa.String(length=255), nullable=True),
        sa.Column("publication_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_translated_optional", sa.Text(), nullable=True),
        sa.Column("buyer", sa.String(length=512), nullable=True),
        sa.Column("buyer_country", sa.String(length=8), nullable=True),
        sa.Column("place_of_performance", sa.String(length=255), nullable=True),
        sa.Column("notice_type", sa.String(length=255), nullable=True),
        sa.Column("procedure_type", sa.String(length=255), nullable=True),
        sa.Column("cpv_codes", sa.JSON(), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contract_duration", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("html_url", sa.String(length=1024), nullable=True),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("xml_url", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_scan_run_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["last_scan_run_id"], ["scan_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_number"),
    )
    op.create_index(op.f("ix_notices_buyer_country"), "notices", ["buyer_country"], unique=False)
    op.create_index(op.f("ix_notices_deadline"), "notices", ["deadline"], unique=False)
    op.create_index(op.f("ix_notices_dismissed"), "notices", ["dismissed"], unique=False)
    op.create_index(op.f("ix_notices_last_scan_run_id"), "notices", ["last_scan_run_id"], unique=False)
    op.create_index(op.f("ix_notices_publication_date"), "notices", ["publication_date"], unique=False)
    op.create_index(op.f("ix_notices_publication_number"), "notices", ["publication_number"], unique=False)
    op.create_index(op.f("ix_notices_saved"), "notices", ["saved"], unique=False)
    op.create_index(op.f("ix_notices_ted_notice_id"), "notices", ["ted_notice_id"], unique=False)

    op.create_table(
        "notice_analysis",
        sa.Column("notice_id", sa.String(length=36), nullable=False),
        sa.Column("scoring_version", sa.String(length=64), nullable=False),
        sa.Column("analysis_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("keyword_hits", sa.JSON(), nullable=False),
        sa.Column("domain_hits", sa.JSON(), nullable=False),
        sa.Column("positive_signals", sa.JSON(), nullable=False),
        sa.Column("negative_signals", sa.JSON(), nullable=False),
        sa.Column("platform_lock_signals", sa.JSON(), nullable=False),
        sa.Column("timing_flags", sa.JSON(), nullable=False),
        sa.Column("rules_fired", sa.JSON(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fit_label", sa.Enum("YES", "CONDITIONAL", "NO", name="fitlabel", native_enum=False), nullable=False),
        sa.Column("priority_bucket", sa.Enum("HIGH", "GOOD", "WATCHLIST", "IGNORE", name="prioritybucket", native_enum=False), nullable=False),
        sa.Column("confidence_indicator", sa.Enum("HIGH", "MEDIUM", "LOW", name="confidenceindicator", native_enum=False), nullable=False),
        sa.Column("qualification_questions", sa.JSON(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("hard_lock_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("soft_lock_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("openness_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("viable_timing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notice_id"], ["notices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notice_id"),
    )
    op.create_index(op.f("ix_notice_analysis_fit_label"), "notice_analysis", ["fit_label"], unique=False)
    op.create_index(op.f("ix_notice_analysis_hard_lock_detected"), "notice_analysis", ["hard_lock_detected"], unique=False)
    op.create_index(op.f("ix_notice_analysis_notice_id"), "notice_analysis", ["notice_id"], unique=False)
    op.create_index(op.f("ix_notice_analysis_priority_bucket"), "notice_analysis", ["priority_bucket"], unique=False)
    op.create_index(op.f("ix_notice_analysis_score"), "notice_analysis", ["score"], unique=False)
    op.create_index(op.f("ix_notice_analysis_scoring_version"), "notice_analysis", ["scoring_version"], unique=False)
    op.create_index(op.f("ix_notice_analysis_viable_timing"), "notice_analysis", ["viable_timing"], unique=False)

    op.create_table(
        "saved_searches",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        sa.Column("query_parameters", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "analyst_notes",
        sa.Column("notice_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notice_id"], ["notices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analyst_notes_notice_id"), "analyst_notes", ["notice_id"], unique=False)
    op.create_index(op.f("ix_analyst_notes_user_id"), "analyst_notes", ["user_id"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_app_settings_key"), "app_settings", ["key"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("event_type", sa.Enum("SCAN_STARTED", "SCAN_COMPLETED", "SCAN_FAILED", "NOTICE_SAVED", "NOTICE_DISMISSED", "NOTE_CREATED", "NOTICE_RESCORED", name="auditeventtype", native_enum=False), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("actor_display_name", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_app_settings_key"), table_name="app_settings")
    op.drop_table("app_settings")
    op.drop_index(op.f("ix_analyst_notes_user_id"), table_name="analyst_notes")
    op.drop_index(op.f("ix_analyst_notes_notice_id"), table_name="analyst_notes")
    op.drop_table("analyst_notes")
    op.drop_table("saved_searches")
    op.drop_index(op.f("ix_notice_analysis_viable_timing"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_scoring_version"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_score"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_priority_bucket"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_notice_id"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_hard_lock_detected"), table_name="notice_analysis")
    op.drop_index(op.f("ix_notice_analysis_fit_label"), table_name="notice_analysis")
    op.drop_table("notice_analysis")
    op.drop_index(op.f("ix_notices_ted_notice_id"), table_name="notices")
    op.drop_index(op.f("ix_notices_saved"), table_name="notices")
    op.drop_index(op.f("ix_notices_publication_number"), table_name="notices")
    op.drop_index(op.f("ix_notices_publication_date"), table_name="notices")
    op.drop_index(op.f("ix_notices_last_scan_run_id"), table_name="notices")
    op.drop_index(op.f("ix_notices_dismissed"), table_name="notices")
    op.drop_index(op.f("ix_notices_deadline"), table_name="notices")
    op.drop_index(op.f("ix_notices_buyer_country"), table_name="notices")
    op.drop_table("notices")
    op.drop_index(op.f("ix_scan_runs_status"), table_name="scan_runs")
    op.drop_table("scan_runs")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

