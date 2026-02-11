"""Initial schema with all models

Revision ID: 5be26697276d
Revises: 
Create Date: 2026-02-10 18:04:16.958192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5be26697276d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for the Data Policy Agent application."""
    
    # Create policies table
    op.create_table(
        'policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_policies_filename', 'policies', ['filename'], unique=False)
    
    # Create compliance_rules table
    op.create_table(
        'compliance_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evaluation_criteria', sa.Text(), nullable=False),
        sa.Column('target_table', sa.String(length=255), nullable=True),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, default='medium'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_compliance_rules_policy_id', 'compliance_rules', ['policy_id'], unique=False)
    op.create_index('ix_compliance_rules_rule_code', 'compliance_rules', ['rule_code'], unique=False)
    
    # Create violations table
    op.create_table(
        'violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_identifier', sa.String(length=255), nullable=False),
        sa.Column('record_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default={}),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('remediation_suggestion', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, default='medium'),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['rule_id'], ['compliance_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_violations_rule_id', 'violations', ['rule_id'], unique=False)
    op.create_index('ix_violations_record_identifier', 'violations', ['record_identifier'], unique=False)
    op.create_index('ix_violations_status', 'violations', ['status'], unique=False)
    
    # Create review_actions table
    op.create_table(
        'review_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('violation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('reviewer_id', sa.String(length=255), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['violation_id'], ['violations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_review_actions_violation_id', 'review_actions', ['violation_id'], unique=False)
    
    # Create database_connections table
    op.create_table(
        'database_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, default=5432),
        sa.Column('database_name', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('encrypted_password', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create scan_history table
    op.create_table(
        'scan_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='running'),
        sa.Column('violations_found', sa.Integer(), nullable=False, default=0),
        sa.Column('new_violations', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create monitoring_config table
    op.create_table(
        'monitoring_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interval_minutes', sa.Integer(), nullable=False, default=360),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('monitoring_config')
    op.drop_table('scan_history')
    op.drop_table('database_connections')
    op.drop_index('ix_review_actions_violation_id', table_name='review_actions')
    op.drop_table('review_actions')
    op.drop_index('ix_violations_status', table_name='violations')
    op.drop_index('ix_violations_record_identifier', table_name='violations')
    op.drop_index('ix_violations_rule_id', table_name='violations')
    op.drop_table('violations')
    op.drop_index('ix_compliance_rules_rule_code', table_name='compliance_rules')
    op.drop_index('ix_compliance_rules_policy_id', table_name='compliance_rules')
    op.drop_table('compliance_rules')
    op.drop_index('ix_policies_filename', table_name='policies')
    op.drop_table('policies')
