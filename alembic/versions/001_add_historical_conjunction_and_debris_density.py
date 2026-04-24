"""Add historical conjunction and debris density tables

Revision ID: 001
Revises: 
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create historical_conjunctions table
    op.create_table(
        'historical_conjunctions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('satellite_id', sa.String(), nullable=False),
        sa.Column('debris_id', sa.String(), nullable=False),
        sa.Column('conjunction_time', sa.DateTime(), nullable=False),
        sa.Column('min_distance_km', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('relative_velocity', sa.Text(), nullable=True),
        sa.Column('probability', sa.Float(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('maneuver_performed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conjunction_time', 'historical_conjunctions', ['conjunction_time'])
    op.create_index('idx_sat_debris', 'historical_conjunctions', ['satellite_id', 'debris_id'])

    # Create debris_density table
    op.create_table(
        'debris_density',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('altitude_min_km', sa.Float(), nullable=False),
        sa.Column('altitude_max_km', sa.Float(), nullable=False),
        sa.Column('object_count', sa.Integer(), nullable=False),
        sa.Column('avg_cross_section', sa.Float(), nullable=True),
        sa.Column('density_per_km3', sa.Float(), nullable=False),
        sa.Column('source', sa.String(), nullable=False, server_default='estimated'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_altitude_range', 'debris_density', ['altitude_min_km', 'altitude_max_km'])


def downgrade():
    op.drop_index('idx_altitude_range', table_name='debris_density')
    op.drop_table('debris_density')
    op.drop_index('idx_sat_debris', table_name='historical_conjunctions')
    op.drop_index('idx_conjunction_time', table_name='historical_conjunctions')
    op.drop_table('historical_conjunctions')
