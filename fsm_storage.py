import json
from collections.abc import Mapping
from typing import Any

from aiogram.exceptions import DataNotDictLikeError
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

import database as db


class PostgresFSMStorage(BaseStorage):
    """Persist aiogram conversation state in the existing PostgreSQL database."""

    def __init__(self) -> None:
        self._state_cache: dict[str, str | None] = {}
        self._data_cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(key: StorageKey) -> str:
        return ":".join(
            [
                str(key.bot_id),
                str(key.chat_id),
                str(key.user_id),
                str(key.thread_id or 0),
                key.business_connection_id or "",
                key.destiny,
            ]
        )

    async def close(self) -> None:
        # The shared pool is closed by database.close_db().
        self._state_cache.clear()
        self._data_cache.clear()
        return None

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        cache_key = self._key(key)
        state_value = state.state if isinstance(state, State) else state
        async with db.db_pool.connection() as conn:
            await conn.execute(
                """INSERT INTO bot_fsm (storage_key, state, data)
                   VALUES (%s, %s, '{}'::jsonb)
                   ON CONFLICT (storage_key) DO UPDATE SET
                       state = EXCLUDED.state,
                       updated_at = CURRENT_TIMESTAMP""",
                (cache_key, state_value),
            )
            await conn.commit()
        self._state_cache[cache_key] = state_value

    async def get_state(self, key: StorageKey) -> str | None:
        cache_key = self._key(key)
        if cache_key in self._state_cache:
            return self._state_cache[cache_key]
        async with db.db_pool.connection() as conn:
            row = await conn.execute(
                "SELECT state FROM bot_fsm WHERE storage_key = %s",
                (cache_key,),
            )
            result = await row.fetchone()
            state = result['state'] if result else None
            self._state_cache[cache_key] = state
            return state

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            raise DataNotDictLikeError(
                f"Data must be a dict or dict-like object, got {type(data).__name__}"
            )
        cache_key = self._key(key)
        serialized = json.dumps(data, ensure_ascii=False, default=str)
        async with db.db_pool.connection() as conn:
            await conn.execute(
                """INSERT INTO bot_fsm (storage_key, state, data)
                   VALUES (%s, NULL, %s::jsonb)
                   ON CONFLICT (storage_key) DO UPDATE SET
                       data = EXCLUDED.data,
                       updated_at = CURRENT_TIMESTAMP""",
                (cache_key, serialized),
            )
            await conn.commit()
        self._data_cache[cache_key] = data.copy()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        cache_key = self._key(key)
        if cache_key in self._data_cache:
            return self._data_cache[cache_key].copy()
        async with db.db_pool.connection() as conn:
            row = await conn.execute(
                "SELECT data FROM bot_fsm WHERE storage_key = %s",
                (cache_key,),
            )
            result = await row.fetchone()
            if not result or not result['data']:
                self._data_cache[cache_key] = {}
                return {}
            value = result['data']
            data = value if isinstance(value, dict) else json.loads(value)
            self._data_cache[cache_key] = data
            return data.copy()
