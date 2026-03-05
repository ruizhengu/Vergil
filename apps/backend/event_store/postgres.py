import os
import asyncio
import logging
from typing import List, Optional

from grafi.common.event_stores.event_store import EventStore
from grafi.common.event_stores.event_store_in_memory import EventStoreInMemory
from grafi.common.event_stores.event_store_postgres import EventStorePostgres
from grafi.common.events.event import Event
from grafi.common.containers.container import container
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DualEventStore(EventStore):
    """
    In-memory for workflow reads (fast, no timing issues).
    PostgreSQL for persistence (writes go to both).
    """

    def __init__(self, memory_store: EventStoreInMemory, pg_store: EventStorePostgres):
        self.memory = memory_store
        self.pg = pg_store

    def _bg_write(self, coro) -> None:
        """Fire-and-forget a PostgreSQL write so it never blocks the workflow."""
        async def _safe():
            try:
                await coro
            except Exception as e:
                logger.error(f"PostgreSQL background write failed: {e}")
        asyncio.create_task(_safe())

    async def record_event(self, event: Event) -> None:
        await self.memory.record_event(event)
        self._bg_write(self.pg.record_event(event))

    async def record_events(self, events: List[Event]) -> None:
        await self.memory.record_events(events)
        self._bg_write(self.pg.record_events(events))

    async def clear_events(self) -> None:
        await self.memory.clear_events()
        self._bg_write(self.pg.clear_events())

    async def get_events(self) -> List[Event]:
        return await self.memory.get_events()

    async def get_event(self, event_id: str) -> Optional[Event]:
        return await self.memory.get_event(event_id)

    async def get_agent_events(self, assistant_request_id: str) -> List[Event]:
        return await self.memory.get_agent_events(assistant_request_id)

    async def get_conversation_events(self, conversation_id: str) -> List[Event]:
        try:
            return await self.pg.get_conversation_events(conversation_id)
        except Exception as e:
            logger.error(f"PostgreSQL get_conversation_events failed: {e}")
            return await self.memory.get_conversation_events(conversation_id)

    async def get_topic_events(self, name: str, offsets: List[int]) -> List[Event]:
        return await self.memory.get_topic_events(name, offsets)


db_url = os.getenv("DATABASE_URL")
if not db_url:
    db_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'postgres')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'postgres')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'vergil')}"
    )

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

try:
    memory_store = EventStoreInMemory()
    pg_store = EventStorePostgres(db_url=db_url)
    dual_store = DualEventStore(memory_store, pg_store)
    container.register_event_store(dual_store)
    logger.info(f"Dual event store registered (in-memory + PostgreSQL)")
except Exception as e:
    logger.error(f"Failed to initialize dual event store: {e}. Using in-memory only.")
