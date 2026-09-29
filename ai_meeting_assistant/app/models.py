from sqlalchemy import Column, Integer, String, ForeignKey, Text
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, index=True)
    audio_path = Column(String, nullable=False)
    transcript = Column(Text)
    summary = Column(Text)
    action_items = Column(Text)
    status = Column(String, default="UPLOADED")
    user_id = Column(Integer, ForeignKey("users.id"))
