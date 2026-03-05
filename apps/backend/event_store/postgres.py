from grafi.common.event_stores.event_store_postgres import EventStorePostgres
from grafi.common.containers.container import container, setup_tracing
from grafi.common.instrumentations.tracing import TracingOptions
from dotenv import load_dotenv

load_dotenv()

import os

db_url = os.getenv("DATABASE_URL")
if not db_url:
    db_url = "postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

# Fix the postgres:// to postgresql:// for SQLAlchemy if DATABASE_URL comes from railway
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
# Also add psycopg2 if it's just postgresql://
elif db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

postgres_event_store = EventStorePostgres(
    db_url=db_url
)

container.register_event_store(postgres_event_store)

    
