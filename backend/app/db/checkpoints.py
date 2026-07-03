from __future__ import annotations

import base64
import json
from typing import Any, Iterator, Sequence, AsyncIterator
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from app.db.session import SessionLocal
from app.db.models import CheckpointRecord

class DatabaseCheckpointSaver(BaseCheckpointSaver):
    """Database-backed LangGraph checkpointer storing checkpoints historically in `checkpoint_records`."""

    def __init__(self, *, serde: Any = None) -> None:
        super().__init__(serde=serde)

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"].get("thread_id")
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if not thread_id:
            return None

        session = SessionLocal()
        try:
            if checkpoint_id:
                rec = (
                    session.query(CheckpointRecord)
                    .filter(
                        CheckpointRecord.thread_id == thread_id,
                        CheckpointRecord.checkpoint_id == checkpoint_id,
                    )
                    .first()
                )
            else:
                rec = (
                    session.query(CheckpointRecord)
                    .filter(CheckpointRecord.thread_id == thread_id)
                    .order_by(CheckpointRecord.created_at.desc(), CheckpointRecord.id.desc())
                    .first()
                )

            if not rec:
                return None

            # Deserialization using loads_typed
            payload = json.loads(rec.checkpoint_data)
            type_str = payload["type"]
            bytes_data = base64.b64decode(payload["data"].encode("utf-8"))
            checkpoint = self.serde.loads_typed((type_str, bytes_data))

            parent_id = checkpoint.get("parent_id")
            parent_config = (
                {"configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}}
                if parent_id
                else None
            )

            # Reconstruct the config with the specific checkpoint_id returned
            final_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": rec.checkpoint_id,
                }
            }

            return CheckpointTuple(
                config=final_config,
                checkpoint=checkpoint,
                metadata=rec.metadata_json or {},
                parent_config=parent_config,
                pending_writes=[],
            )
        finally:
            session.close()

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"].get("thread_id")
        checkpoint_id = checkpoint.get("id")
        if not thread_id or not checkpoint_id:
            return config

        session = SessionLocal()
        try:
            # Check if this exact checkpoint already exists to avoid duplicates
            exists = (
                session.query(CheckpointRecord)
                .filter(
                    CheckpointRecord.thread_id == thread_id,
                    CheckpointRecord.checkpoint_id == checkpoint_id,
                )
                .first()
            )
            if not exists:
                # Serialization using dumps_typed
                type_str, bytes_data = self.serde.dumps_typed(checkpoint)
                base64_str = base64.b64encode(bytes_data).decode("utf-8")
                serialized_data = json.dumps({"type": type_str, "data": base64_str})

                rec = CheckpointRecord(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    checkpoint_data=serialized_data,
                    metadata_json=metadata,
                )
                session.add(rec)
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    def list(
        self,
        config: RunnableConfig | None,
        *,
        before: CheckpointTuple | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if not config:
            return

        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            return

        session = SessionLocal()
        try:
            query = session.query(CheckpointRecord).filter(CheckpointRecord.thread_id == thread_id)
            
            if before and before.config:
                before_id = before.config["configurable"].get("checkpoint_id")
                if before_id:
                    # Fetch target to check timestamp threshold
                    before_rec = (
                        session.query(CheckpointRecord)
                        .filter(
                            CheckpointRecord.thread_id == thread_id,
                            CheckpointRecord.checkpoint_id == before_id,
                        )
                        .first()
                    )
                    if before_rec:
                        query = query.filter(CheckpointRecord.created_at < before_rec.created_at)

            query = query.order_by(CheckpointRecord.created_at.desc(), CheckpointRecord.id.desc())
            if limit:
                query = query.limit(limit)

            records = query.all()
            for rec in records:
                # Deserialization using loads_typed
                payload = json.loads(rec.checkpoint_data)
                type_str = payload["type"]
                bytes_data = base64.b64decode(payload["data"].encode("utf-8"))
                checkpoint = self.serde.loads_typed((type_str, bytes_data))

                parent_id = checkpoint.get("parent_id")
                parent_config = (
                    {"configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}}
                    if parent_id
                    else None
                )
                yield CheckpointTuple(
                    config={"configurable": {"thread_id": thread_id, "checkpoint_id": rec.checkpoint_id}},
                    checkpoint=checkpoint,
                    metadata=rec.metadata_json or {},
                    parent_config=parent_config,
                    pending_writes=[],
                )
        finally:
            session.close()

    # Async equivalents for async execution compatibility
    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        before: CheckpointTuple | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for tup in self.list(config, before=before, limit=limit):
            yield tup
