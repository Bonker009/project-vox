from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4
from app.database import Base  # Import your Base

class OTP(Base):
    __tablename__ = "otp"

    otps_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    otps_code = Column(String(6), nullable=False, unique=True)
    issued_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expired_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP + INTERVAL '2 minutes'"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.user_id", ondelete="CASCADE", onupdate="CASCADE"))

    # Relationship to User
    user = relationship("User", back_populates="otps")
