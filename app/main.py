from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — registers all ORM models with SQLAlchemy metadata
from app.api import routes_admin, routes_metals, routes_items
from app.config.settings import allowed_origins
from app.db.database import Base, engine

# Create all tables on startup (use Alembic migrations in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Gold Shop API",
    description="Jewelry inventory backend for a gold shop — supports EN/ES.",
    version="1.0.0",
)

# CORS — origins loaded from ALLOWED_ORIGINS env variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_items.router)
app.include_router(routes_admin.router)
app.include_router(routes_metals.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
