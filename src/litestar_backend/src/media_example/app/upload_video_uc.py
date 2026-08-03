import hashlib
from dataclasses import dataclass, field
from typing import Any

import msgspec

from shared.app import IClock
from shared.generics.errors import PortError
from shared.logging import Layer, layer_logger

from ..domain import Video
from .errors import IdempotencyKeyReused
from .interfaces import IIdempotencyStore, IOutboxRepo, IUoW, IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoCommand:
    source_key: str
    document: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadResult:
    video: Video
    replayed: bool


def _canonical(value: Any) -> Any:
    # Sort mapping keys at every depth so two retries that serialise the same
    # payload in a different key order hash identically -- otherwise an honest
    # retry would look like key reuse and get rejected.
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def _fingerprint(command: UploadVideoCommand) -> str:
    payload = _canonical({"source_key": command.source_key, "document": command.document})
    return hashlib.sha256(msgspec.json.encode(payload)).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoUC:
    _repo: IVideoRepo
    _uow: IUoW
    _outbox: IOutboxRepo
    _clock: IClock
    _idempotency: IIdempotencyStore

    async def __call__(self, command: UploadVideoCommand) -> UploadResult:
        video = Video.upload(
            source_key=command.source_key,
            uploaded_at=self._clock.now(),
            document=command.document,
        )
        key = command.idempotency_key
        fingerprint = _fingerprint(command) if key is not None else ""

        claimed = True
        async with self._uow:
            if key is not None:
                claimed = await self._idempotency.claim(key, fingerprint=fingerprint, video=video)
            if claimed:
                await self._repo.save(video)
                for event in video.collect_events():
                    await self._outbox.add(event)

        if claimed or key is None:
            # Backend edge of the cross-service correlation chain: video_id logged
            # here lets a grep across both services follow the whole causal chain;
            # trace_id (merged via contextvar) pins it to the originating request.
            # Built at the call site (S-DDD logging rule 3: bind layer at the
            # operation boundary), not as a module global -- see structlog.md.
            layer_logger(Layer.APP, "UploadVideoUC").info(
                "video registered", video_id=str(video.id)
            )
            return UploadResult(video=video, replayed=False)

        # Lost the claim: the key was committed by a concurrent or earlier
        # request and this transaction wrote nothing. The winner's row is
        # committed by construction -- claim() only reports False against a
        # visible row.
        stored = await self._idempotency.find(key)
        if stored is None:
            raise PortError(f"idempotency key {key} was claimed but is no longer readable")
        if stored.fingerprint != fingerprint:
            raise IdempotencyKeyReused(key)
        layer_logger(Layer.APP, "UploadVideoUC").info(
            "upload replayed", video_id=str(stored.video.id)
        )
        return UploadResult(video=stored.video, replayed=True)
