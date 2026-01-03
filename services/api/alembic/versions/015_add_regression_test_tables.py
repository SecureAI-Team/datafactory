"""Add regression test tables

Revision ID: 015
Revises: 014
Create Date: 2026-01-03

Creates tables for regression testing functionality:
- regression_test_cases: Test case definitions
- regression_test_runs: Test execution runs
- regression_test_results: Individual test results
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create regression_test_cases table
    op.create_table(
        'regression_test_cases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),  # rag/llm/e2e
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('expected_ku_ids', JSONB, server_default='[]'),
        sa.Column('expected_answer', sa.Text()),
        sa.Column('evaluation_criteria', JSONB, server_default='{}'),
        sa.Column('tags', JSONB, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_by', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_regression_cases_category', 'regression_test_cases', ['category'])
    op.create_index('idx_regression_cases_active', 'regression_test_cases', ['is_active'])

    # Create regression_test_runs table
    op.create_table(
        'regression_test_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.String(50), unique=True, nullable=False),
        sa.Column('status', sa.String(20), server_default='running'),  # running/completed/failed
        sa.Column('total_cases', sa.Integer(), server_default='0'),
        sa.Column('passed_cases', sa.Integer(), server_default='0'),
        sa.Column('failed_cases', sa.Integer(), server_default='0'),
        sa.Column('review_cases', sa.Integer(), server_default='0'),
        sa.Column('pass_rate', sa.Float()),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('triggered_by', sa.String(50)),
        sa.Column('config', JSONB, server_default='{}'),  # Run configuration
    )
    op.create_index('idx_regression_runs_status', 'regression_test_runs', ['status'])
    op.create_index('idx_regression_runs_started', 'regression_test_runs', ['started_at'])

    # Create regression_test_results table
    op.create_table(
        'regression_test_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('regression_test_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('regression_test_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actual_answer', sa.Text()),
        sa.Column('retrieved_ku_ids', JSONB, server_default='[]'),
        sa.Column('retrieval_score', sa.Float()),
        sa.Column('answer_score', sa.Float()),
        sa.Column('llm_evaluation', JSONB),  # Detailed LLM evaluation
        sa.Column('manual_review', sa.String(20), server_default='pending'),  # pending/pass/fail
        sa.Column('manual_comment', sa.Text()),
        sa.Column('reviewed_by', sa.String(50)),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('execution_time_ms', sa.Integer()),
        sa.Column('status', sa.String(20), server_default='pending'),  # pass/fail/review/pending
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_regression_results_run', 'regression_test_results', ['run_id'])
    op.create_index('idx_regression_results_case', 'regression_test_results', ['case_id'])
    op.create_index('idx_regression_results_status', 'regression_test_results', ['status'])
    op.create_index('idx_regression_results_review', 'regression_test_results', ['manual_review'])


def downgrade() -> None:
    op.drop_table('regression_test_results')
    op.drop_table('regression_test_runs')
    op.drop_table('regression_test_cases')

