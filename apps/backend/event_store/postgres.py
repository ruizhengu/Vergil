from grafi.common.event_stores.event_store_postgres import EventStorePostgres
from grafi.common.containers.container import container, setup_tracing
from grafi.common.instrumentations.tracing import TracingOptions
from dotenv import load_dotenv

load_dotenv()

postgres_event_store = EventStorePostgres(
    db_url="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
)

container.register_event_store(postgres_event_store)

    
