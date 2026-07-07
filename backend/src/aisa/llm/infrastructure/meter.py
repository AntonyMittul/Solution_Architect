from redis.asyncio import Redis


class RedisRunTokenMeter:
    """Per-run token counter in Redis (O(1) INCRBY). Keys expire so counters
    for old runs don't accumulate."""

    def __init__(self, redis: Redis, ttl_seconds: int = 86_400) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def add(self, run_id: str, tokens: int) -> int:
        key = f"aisa:run:{run_id}:tokens"
        total = int(await self._redis.incrby(key, tokens))
        await self._redis.expire(key, self._ttl)
        return total


class NullRunTokenMeter:
    async def add(self, run_id: str, tokens: int) -> int:
        return 0
