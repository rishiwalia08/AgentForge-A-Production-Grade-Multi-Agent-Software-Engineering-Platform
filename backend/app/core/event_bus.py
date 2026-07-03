from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable
import redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class EventManager:
    """Redis Pub/Sub backed event bus with fallback to in-memory queues for unit testing."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], Any]]] = {}
        self._use_redis = False
        self._redis_client: redis.Redis | None = None
        self._redis_threads: dict[str, threading.Thread] = {}

        # Initialize Redis in non-testing environments
        if settings.environment != "test":
            try:
                self._redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                self._redis_client.ping()
                self._use_redis = True
                logger.info("EventManager successfully connected to Redis Pub/Sub Event Bus")
            except Exception as e:
                logger.warning(f"Redis not available ({e}). EventManager falling back to local memory event bus.")

    def subscribe(self, run_id: str, callback: Callable[[dict[str, Any]], Any]) -> None:
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(callback)

        # Start a Redis listener thread if not already running for this run_id
        if self._use_redis and run_id not in self._redis_threads and self._redis_client:
            thread = threading.Thread(
                target=self._redis_listen_loop,
                args=(run_id,),
                daemon=True
            )
            self._redis_threads[run_id] = thread
            thread.start()

    def unsubscribe(self, run_id: str, callback: Callable[[dict[str, Any]], Any]) -> None:
        if run_id in self._subscribers:
            try:
                self._subscribers[run_id].remove(callback)
            except ValueError:
                pass
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]
                # Thread will naturally close when channel receives termination or unsubscribes

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        if self._use_redis and self._redis_client:
            try:
                channel = f"run:{run_id}"
                self._redis_client.publish(channel, json.dumps(event))
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}", exc_info=True)
                # Fallback to local memory dispatch if Redis publish fails
                self._local_publish(run_id, event)
        else:
            self._local_publish(run_id, event)

    def _local_publish(self, run_id: str, event: dict[str, Any]) -> None:
        if run_id in self._subscribers:
            for callback in self._subscribers[run_id]:
                try:
                    callback(event)
                except Exception:
                    pass

    def _redis_listen_loop(self, run_id: str) -> None:
        if not self._redis_client:
            return
        
        pubsub = self._redis_client.pubsub()
        channel = f"run:{run_id}"
        pubsub.subscribe(channel)
        logger.debug(f"Redis listener thread started for channel: {channel}")
        
        try:
            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        # Trigger local websocket callbacks
                        self._local_publish(run_id, event_data)
                        
                        # Stop listening if run reaches end of lifecycle
                        if event_data.get("type") in ("completed", "failed"):
                            logger.debug(f"Lifecycle event '{event_data['type']}' received. Stopping Redis listener for {channel}.")
                            break
                    except Exception as parse_err:
                        logger.error(f"Error parsing Redis message: {parse_err}")
        except Exception as conn_err:
            logger.error(f"Redis pub/sub listen error on {channel}: {conn_err}")
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass
            self._redis_threads.pop(run_id, None)
            logger.debug(f"Redis listener thread stopped for channel: {channel}")

# Expose global EventManager singleton
event_manager = EventManager()
