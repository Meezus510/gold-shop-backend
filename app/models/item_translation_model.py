from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class ItemTranslation(Base):
    __tablename__ = "item_translations"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False)
    language = Column(String(5), nullable=False)  # "en" or "es"
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    item = relationship("Item", back_populates="translations")
