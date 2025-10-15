# app/models/bus_location.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from ..database import Base

if TYPE_CHECKING:
    from .bus import Bus


class BusLocation(Base):
    __tablename__ = "bus_locations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"))
    latitude: Mapped[float] = mapped_column(DECIMAL(10, 8))
    longitude: Mapped[float] = mapped_column(DECIMAL(11, 8))
    speed: Mapped[float] = mapped_column(DECIMAL)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # İlişkiler
    bus: Mapped["Bus"] = relationship(
        "Bus", back_populates="bus_locations"
    )