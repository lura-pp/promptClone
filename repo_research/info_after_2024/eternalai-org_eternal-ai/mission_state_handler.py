from x_content.cache.base_state_handler import StatusHandlerBase
from x_content.constants import MissionChainState
from x_content.models import ReasoningLog
import redis
from redis import asyncio as aredis
from x_content.wrappers.redis_wrapper import get_redis_connection_pool, get_aio_redis_connection_pool
import json
from typing import Optional, List
import traceback
from pydantic_core import from_json
from x_content import constants as const


class MissionStateHandler(StatusHandlerBase[ReasoningLog]):
    BASE_KEY = const.REDIS_LOG_BASE_KEY

    def __init__(self) -> None:
        self.cache_expiry = 3 * 24 * 3600  # Cache entries for 3 * 24 hours

    def commit(self, state: ReasoningLog) -> ReasoningLog:
        key = f"{self.BASE_KEY}:{state.id}"
        jsons = json.dumps(state.model_dump())
        
        with redis.Redis(connection_pool=get_redis_connection_pool()) as cli:
            cli.setex(key, self.cache_expiry, jsons)

        return state

    async def acommit(self, state: ReasoningLog) -> ReasoningLog:
        key = f"{self.BASE_KEY}:{state.id}"
        jsons = json.dumps(state.model_dump())

        async with aredis.Redis(
            connection_pool=get_aio_redis_connection_pool()
        ) as redis:
            await redis.setex(key, self.cache_expiry, jsons)

        return state

    def get_undone(self) -> List[ReasoningLog]:
        states = []

        with redis.Redis(connection_pool=get_redis_connection_pool()) as cli:
            keys = cli.keys(f"{self.BASE_KEY}:*")

            for key in keys:

                try:
                    state = ReasoningLog.model_validate(
                        from_json(cli.get(key).decode("utf-8"))
                    )
                except ValueError:
                    continue

                if not state.is_done() and not state.is_error():
                    states.append(state)

        return states

    async def a_get(
        self, _id: str, none_if_error: bool = False
    ) -> Optional[ReasoningLog]:
        key = f"{self.BASE_KEY}:{_id}"
        cli = aredis.Redis(connection_pool=get_aio_redis_connection_pool())
        json_state: Optional[bytes] = await cli.get(key)

        if json_state is not None:
            try:
                state = ReasoningLog.model_validate(
                    from_json(json_state.decode("utf-8"))
                )

            except ValueError as err:
                traceback.print_exc()

                if none_if_error:
                    return None

                # Fallback to error state if JSON deserialization fails
                state = ReasoningLog(
                    state=MissionChainState.ERROR,
                    id=_id,
                    system_message=f"{_id} JSON deserialization failed",
                    prompt="",
                    meta_data=None,
                )
        else:
            if none_if_error:
                return None

            # Return an error state if the state doesn't exist in Redis
            state = ReasoningLog(
                state=MissionChainState.ERROR,
                id=_id,
                system_message=f"{_id} Not found",
                prompt="",
                meta_data=None,
            )

        # Update the cache expiry time
        await cli.expire(key, self.cache_expiry)
        return state

    def get(
        self, _id: str, none_if_error: bool = False
    ) -> Optional[ReasoningLog]:
        key = f"{self.BASE_KEY}:{_id}"
        cli = redis.Redis(connection_pool=get_redis_connection_pool())
        json_state: Optional[bytes] = cli.get(key)

        if json_state is not None:
            try:
                state = ReasoningLog.model_validate(
                    from_json(json_state.decode("utf-8"))
                )

            except ValueError as err:
                traceback.print_exc()

                if none_if_error:
                    return None

                # Fallback to error state if JSON deserialization fails
                state = ReasoningLog(
                    state=MissionChainState.ERROR,
                    id=_id,
                    system_message=f"{_id} JSON deserialization failed",
                    prompt="",
                    meta_data=None,
                )
        else:
            if none_if_error:
                return None

            # Return an error state if the state doesn't exist in Redis
            state = ReasoningLog(
                state=MissionChainState.ERROR,
                id=_id,
                system_message=f"{_id} Not found",
                prompt="",
                meta_data=None,
            )

        # Update the cache expiry time
        cli.expire(key, self.cache_expiry)
        return state
