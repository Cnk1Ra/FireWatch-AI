"""
Initial migration - Create all tables

Revision ID: 001_initial
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# Revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables."""

    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Create hotspots table
    op.create_table(
        'hotspots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('location', Geometry('POINT', srid=4326), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('brightness', sa.Float(), nullable=False),
        sa.Column('frp', sa.Float(), nullable=False),
        sa.Column('confidence', sa.String(20), nullable=False),
        sa.Column('acq_datetime', sa.DateTime(), nullable=False),
        sa.Column('satellite', sa.String(50), nullable=False),
        sa.Column('daynight', sa.String(1), nullable=False),
        sa.Column('biome', sa.String(50)),
        sa.Column('state', sa.String(50)),
        sa.Column('cluster_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('source', sa.String(50), server_default='VIIRS_NOAA20_NRT'),
    )

    op.create_index('idx_hotspot_location', 'hotspots', ['location'], postgresql_using='gist')
    op.create_index('idx_hotspot_acq_datetime', 'hotspots', ['acq_datetime'])
    op.create_index('idx_hotspot_state_biome', 'hotspots', ['state', 'biome'])

    # Create fire_clusters table
    op.create_table(
        'fire_clusters',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('center', Geometry('POINT', srid=4326), nullable=False),
        sa.Column('center_lat', sa.Float(), nullable=False),
        sa.Column('center_lon', sa.Float(), nullable=False),
        sa.Column('hotspot_count', sa.Integer(), server_default='0'),
        sa.Column('total_frp', sa.Float(), server_default='0'),
        sa.Column('max_frp', sa.Float(), server_default='0'),
        sa.Column('avg_frp', sa.Float(), server_default='0'),
        sa.Column('estimated_area_ha', sa.Float(), server_default='0'),
        sa.Column('perimeter', Geometry('POLYGON', srid=4326)),
        sa.Column('biome', sa.String(50)),
        sa.Column('state', sa.String(50)),
        sa.Column('first_detected', sa.DateTime(), nullable=False),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('risk_level', sa.String(20), server_default='MODERADO'),
        sa.Column('spread_rate', sa.Float()),
        sa.Column('spread_direction', sa.Float()),
        sa.Column('metadata', sa.JSON(), server_default='{}'),
    )

    op.create_index('idx_cluster_center', 'fire_clusters', ['center'], postgresql_using='gist')
    op.create_index('idx_cluster_active', 'fire_clusters', ['is_active'])
    op.create_index('idx_cluster_first_detected', 'fire_clusters', ['first_detected'])

    # Add foreign key for hotspots -> clusters
    op.create_foreign_key(
        'fk_hotspot_cluster',
        'hotspots', 'fire_clusters',
        ['cluster_id'], ['id']
    )

    # Create weather_records table
    op.create_table(
        'weather_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('location', Geometry('POINT', srid=4326), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('humidity', sa.Float(), nullable=False),
        sa.Column('wind_speed', sa.Float(), nullable=False),
        sa.Column('wind_direction', sa.Float(), nullable=False),
        sa.Column('precipitation', sa.Float(), server_default='0'),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('source', sa.String(50), server_default='open-meteo'),
    )

    op.create_index('idx_weather_location', 'weather_records', ['location'], postgresql_using='gist')
    op.create_index('idx_weather_recorded_at', 'weather_records', ['recorded_at'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('location', Geometry('POINT', srid=4326)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('state', sa.String(50)),
        sa.Column('biome', sa.String(50)),
        sa.Column('cluster_id', sa.Integer(), sa.ForeignKey('fire_clusters.id')),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('acknowledged', sa.Boolean(), server_default='false'),
        sa.Column('acknowledged_at', sa.DateTime()),
        sa.Column('acknowledged_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('email_sent', sa.Boolean(), server_default='false'),
        sa.Column('sms_sent', sa.Boolean(), server_default='false'),
        sa.Column('push_sent', sa.Boolean(), server_default='false'),
    )

    op.create_index('idx_alert_level', 'alerts', ['level'])
    op.create_index('idx_alert_active', 'alerts', ['is_active'])
    op.create_index('idx_alert_created_at', 'alerts', ['created_at'])

    # Create user_reports table
    op.create_table(
        'user_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('location', Geometry('POINT', srid=4326), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('photo_url', sa.String(500)),
        sa.Column('has_flames', sa.Boolean(), server_default='true'),
        sa.Column('has_smoke', sa.Boolean(), server_default='true'),
        sa.Column('estimated_size', sa.String(20)),
        sa.Column('reporter_name', sa.String(100)),
        sa.Column('reporter_phone', sa.String(20)),
        sa.Column('reporter_email', sa.String(100)),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('validated_by', sa.String(100)),
        sa.Column('validated_at', sa.DateTime()),
        sa.Column('matched_hotspot_id', sa.Integer(), sa.ForeignKey('hotspots.id')),
        sa.Column('ml_confidence', sa.Float()),
        sa.Column('reported_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index('idx_report_location', 'user_reports', ['location'], postgresql_using='gist')
    op.create_index('idx_report_status', 'user_reports', ['status'])
    op.create_index('idx_report_reported_at', 'user_reports', ['reported_at'])

    # Create biome_areas table
    op.create_table(
        'biome_areas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('area', Geometry('MULTIPOLYGON', srid=4326), nullable=False),
        sa.Column('carbon_tons_ha', sa.Float(), nullable=False),
        sa.Column('recovery_years', sa.Integer(), nullable=False),
        sa.Column('spread_factor', sa.Float(), server_default='1.0'),
        sa.Column('total_area_km2', sa.Float()),
        sa.Column('fire_count_year', sa.Integer(), server_default='0'),
        sa.Column('burned_area_year_ha', sa.Float(), server_default='0'),
        sa.Column('metadata', sa.JSON(), server_default='{}'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index('idx_biome_area', 'biome_areas', ['area'], postgresql_using='gist')


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('user_reports')
    op.drop_table('alerts')
    op.drop_table('weather_records')
    op.drop_table('hotspots')
    op.drop_table('fire_clusters')
    op.drop_table('biome_areas')
