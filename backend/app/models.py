from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from app.database import Base


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=True)
    album = Column(String(255), nullable=True)
    file_path = Column(Text, nullable=False)
    format = Column(String(50), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)