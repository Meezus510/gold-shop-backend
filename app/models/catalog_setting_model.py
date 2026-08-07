from sqlalchemy import Boolean, Column, Integer

from app.db.database import Base


class CatalogSetting(Base):
    __tablename__ = "catalog_settings"

    id = Column(Integer, primary_key=True, default=1)
    use_enhanced_images = Column(Boolean, nullable=False, default=False)
