"""Placeholder background worker (Docker `worker` service).
Connects to Redis and stays alive. Long simulation jobs can be added here later;
until then it only proves that Redis and the worker container are wired up."""
import logging
import os
import time

import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(message)s")
log = logging.getLogger("genesis.worker")


def main():
    client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    while True:
        try:
            client.ping()
            log.info("redis ok, waiting for jobs")
            time.sleep(30)
        except redis.RedisError as exc:
            log.warning("redis not ready: %s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
