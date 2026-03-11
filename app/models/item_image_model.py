from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class ItemImage(Base):
    __tablename__ = "item_images"

    id       = Column(Integer, primary_key=True, index=True)
    item_id  = Column(Integer, ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False, index=True)
    url      = Column(String, nullable=False)
    position = Column(Integer, nullable=False, default=0)  # 0 = primary / thumbnail

    item = relationship("Item", back_populates="images")
