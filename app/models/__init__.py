# Import all models so SQLAlchemy's Base.metadata knows about every table.
from app.models.admin_model import Admin  # noqa: F401
from app.models.metal_model import Metal  # noqa: F401
from app.models.item_model import Item  # noqa: F401
from app.models.item_translation_model import ItemTranslation  # noqa: F401
