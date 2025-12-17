from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(32), nullable=True, unique=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    # Role-based access control: Admin, OperatorManager, Agent
    role = Column(String(50), nullable=False, default="Agent", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Operator(Base):
    __tablename__ = "operators"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    buses = relationship("Bus", back_populates="operator")


class Bus(Base):
    __tablename__ = "buses"
    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    registration_number = Column(String(64), nullable=False, unique=True, index=True)
    capacity = Column(Integer, nullable=False, default=0)
    model = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    operator = relationship("Operator", back_populates="buses")
    seatmaps = relationship("SeatMap", back_populates="bus")


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    origin = Column(String(128), nullable=False, index=True)
    destination = Column(String(128), nullable=False, index=True)
    distance_km = Column(Numeric(8, 2), nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("origin", "destination", name="uq_route_origin_destination"),)


class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    departure_time = Column(DateTime(timezone=True), nullable=False, index=True)
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="scheduled", index=True)
    seats_available = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships can be added as needed


class SeatMap(Base):
    __tablename__ = "seatmaps"
    id = Column(Integer, primary_key=True)
    bus_id = Column(Integer, ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    layout = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bus = relationship("Bus", back_populates="seatmaps")
    seats = relationship("Seat", back_populates="seatmap")


class Seat(Base):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True)
    seatmap_id = Column(Integer, ForeignKey("seatmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number = Column(String(32), nullable=False)
    row = Column(Integer, nullable=True)
    column = Column(Integer, nullable=True)
    is_window = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    seatmap = relationship("SeatMap", back_populates="seats")

    __table_args__ = (UniqueConstraint("seatmap_id", "seat_number", name="uq_seatmap_seat_number"),)


class Fare(Base):
    __tablename__ = "fares"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="UGX")
    travel_class = Column(String(50), nullable=False, default="economy")
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_fare_route_class", "route_id", "travel_class"),)


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    booked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("trip_id", "seat_id", name="uq_trip_seat"),)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="UGX")
    provider = Column(String(128), nullable=True)
    provider_ref = Column(String(255), nullable=True, unique=True)
    status = Column(String(50), nullable=False, default="initiated", index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_number = Column(String(128), nullable=False, unique=True, index=True)
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    message = Column(String(1024), nullable=False)
    channel = Column(String(64), nullable=False, default="email")
    sent_at = Column(DateTime(timezone=True), nullable=True)
    read = Column(Boolean, default=False, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(255), nullable=False)
    object_type = Column(String(128), nullable=True)
    object_id = Column(String(128), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
