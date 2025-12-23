from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String),
        sa.Column("uploader", sa.String),
        sa.Column("mime", sa.String),
        sa.Column("size", sa.Integer),
        sa.Column("hash", sa.String),
        sa.Column("minio_uri", sa.String),
        sa.Column("status", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "extracted_texts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_document_id", sa.Integer, sa.ForeignKey("source_documents.id")),
        sa.Column("tika_text", sa.Text),
        sa.Column("metadata_json", sa.JSON),
        sa.Column("unstructured_elements_json", sa.JSON),
        sa.Column("status", sa.String),
    )
    op.create_table(
        "knowledge_units",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer),
        sa.Column("status", sa.String),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("body_markdown", sa.Text, nullable=False),
        sa.Column("sections_json", sa.JSON),
        sa.Column("tags_json", sa.JSON),
        sa.Column("glossary_terms_json", sa.JSON),
        sa.Column("evidence_map_json", sa.JSON),
        sa.Column("source_refs_json", sa.JSON),
        sa.Column("created_by", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ku_reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ku_id", sa.Integer, sa.ForeignKey("knowledge_units.id")),
        sa.Column("reviewer", sa.String),
        sa.Column("decision", sa.String),
        sa.Column("comments", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String),
        sa.Column("user_id", sa.String),
        sa.Column("scenario_id", sa.String),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id")),
        sa.Column("message_id", sa.String),
        sa.Column("rating", sa.Integer),
        sa.Column("reason_enum", sa.String),
        sa.Column("comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "scenario_prompts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("input_schema_json", sa.JSON),
        sa.Column("output_schema_json", sa.JSON),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dq_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.String),
        sa.Column("suite_name", sa.String),
        sa.Column("passed", sa.Boolean),
        sa.Column("report_uri", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dag_id", sa.String),
        sa.Column("run_id", sa.String),
        sa.Column("status", sa.String),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text),
    )

def downgrade():
    pass
