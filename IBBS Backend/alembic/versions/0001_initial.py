"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2025-12-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated ###
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('email', name='users_email_key'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    op.create_table('operators',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('name', name='operators_name_key'),
    )
    op.create_index('ix_operators_name', 'operators', ['name'], unique=False)

    op.create_table('buses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('operator_id', sa.Integer(), nullable=True),
        sa.Column('registration_number', sa.String(length=64), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['operator_id'], ['operators.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('registration_number', name='buses_registration_number_key'),
    )
    op.create_index('ix_buses_registration_number', 'buses', ['registration_number'], unique=False)
    op.create_index('ix_buses_operator_id', 'buses', ['operator_id'], unique=False)

    op.create_table('routes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('origin', sa.String(length=128), nullable=False),
        sa.Column('destination', sa.String(length=128), nullable=False),
        sa.Column('distance_km', sa.Numeric(8, 2), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('origin', 'destination', name='uq_route_origin_destination'),
    )
    op.create_index('ix_routes_origin', 'routes', ['origin'], unique=False)
    op.create_index('ix_routes_destination', 'routes', ['destination'], unique=False)

    op.create_table('trips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('route_id', sa.Integer(), nullable=False),
        sa.Column('bus_id', sa.Integer(), nullable=True),
        sa.Column('operator_id', sa.Integer(), nullable=True),
        sa.Column('departure_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('arrival_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='scheduled'),
        sa.Column('seats_available', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['operator_id'], ['operators.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_trips_route_id', 'trips', ['route_id'], unique=False)
    op.create_index('ix_trips_departure_time', 'trips', ['departure_time'], unique=False)

    op.create_table('seatmaps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bus_id', sa.Integer(), nullable=False),
        sa.Column('layout', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bus_id'], ['buses.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_seatmaps_bus_id', 'seatmaps', ['bus_id'], unique=False)

    op.create_table('seats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('seatmap_id', sa.Integer(), nullable=False),
        sa.Column('seat_number', sa.String(length=32), nullable=False),
        sa.Column('row', sa.Integer(), nullable=True),
        sa.Column('column', sa.Integer(), nullable=True),
        sa.Column('is_window', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['seatmap_id'], ['seatmaps.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('seatmap_id', 'seat_number', name='uq_seatmap_seat_number'),
    )
    op.create_index('ix_seats_seatmap_id', 'seats', ['seatmap_id'], unique=False)

    op.create_table('fares',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('route_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UGX'),
        sa.Column('travel_class', sa.String(length=50), nullable=False, server_default='economy'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_fare_route_class', 'fares', ['route_id', 'travel_class'], unique=False)

    op.create_table('bookings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('seat_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('booked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('trip_id', 'seat_id', name='uq_trip_seat'),
    )
    op.create_index('ix_bookings_trip_id', 'bookings', ['trip_id'], unique=False)

    op.create_table('payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UGX'),
        sa.Column('provider', sa.String(length=128), nullable=True),
        sa.Column('provider_ref', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='initiated'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('provider_ref', name='payments_provider_ref_key'),
    )
    op.create_index('ix_payments_booking_id', 'payments', ['booking_id'], unique=False)

    op.create_table('tickets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('ticket_number', sa.String(length=128), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('meta', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('ticket_number', name='tickets_ticket_number_key'),
    )
    op.create_index('ix_tickets_booking_id', 'tickets', ['booking_id'], unique=False)

    op.create_table('notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('message', sa.String(length=1024), nullable=False),
        sa.Column('channel', sa.String(length=64), nullable=False, server_default='email'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)

    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('object_type', sa.String(length=128), nullable=True),
        sa.Column('object_id', sa.String(length=128), nullable=True),
        sa.Column('detail', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'], unique=False)

    # seed routes for Uganda
    op.execute(
        """
        INSERT INTO routes (origin, destination, distance_km, active, created_at)
        VALUES
        ('Kampala','Gulu', 330.00, true, now()),
        ('Kampala','Arua', 420.00, true, now()),
        ('Kampala','Mbale', 225.00, true, now())
        ON CONFLICT DO NOTHING;
        """
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_index('ix_audit_logs_actor_id', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_tickets_booking_id', table_name='tickets')
    op.drop_table('tickets')
    op.drop_index('ix_payments_booking_id', table_name='payments')
    op.drop_table('payments')
    op.drop_index('ix_bookings_trip_id', table_name='bookings')
    op.drop_table('bookings')
    op.drop_index('ix_fare_route_class', table_name='fares')
    op.drop_table('fares')
    op.drop_index('ix_seats_seatmap_id', table_name='seats')
    op.drop_table('seats')
    op.drop_index('ix_seatmaps_bus_id', table_name='seatmaps')
    op.drop_table('seatmaps')
    op.drop_index('ix_trips_departure_time', table_name='trips')
    op.drop_index('ix_trips_route_id', table_name='trips')
    op.drop_table('trips')
    op.drop_index('ix_routes_destination', table_name='routes')
    op.drop_index('ix_routes_origin', table_name='routes')
    op.drop_table('routes')
    op.drop_index('ix_buses_operator_id', table_name='buses')
    op.drop_index('ix_buses_registration_number', table_name='buses')
    op.drop_table('buses')
    op.drop_index('ix_operators_name', table_name='operators')
    op.drop_table('operators')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
