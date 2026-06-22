"""Regression tests for datetime serialization on DB-backed models.

The ``created_at`` / ``updated_at`` columns use ``DateTime(timezone=True)``,
which SQLite returns as naive on read. A ``@field_serializer`` stamps them back
to UTC ISO strings so the frontend parses them correctly.

The serializer must take ``self`` (not ``cls``): Pydantic calls it as an
instance method, so a ``cls`` first parameter shifts ``value`` onto the
``SerializationInfo`` argument and serializes to ``None`` — which made reloaded
chat timestamps disappear.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from magentic_ui.backend.database.db_manager import DatabaseManager
from magentic_ui.backend.datamodel.db import Message, Run, RunStatus, Session


@pytest.fixture
def db(tmp_path: Path) -> DatabaseManager:
    """A real DatabaseManager on a temp SQLite file.

    Uses the production engine (FK enforcement, StaticPool, PRAGMAs) instead of
    a bare in-memory engine, so the tests exercise real behavior.
    """
    manager = DatabaseManager(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(manager.engine)
    return manager


def _seed_message(db: DatabaseManager) -> Message:
    """Insert a session, run, and message (satisfying foreign keys), then read
    the message back so it goes through the API's load path (naive datetimes,
    empty ``model_fields_set``)."""
    with DBSession(db.engine) as session:
        parent = Session(user_id="u", name="t")
        session.add(parent)
        session.commit()
        session.refresh(parent)

        run = Run(
            session_id=parent.id,
            status=RunStatus.CREATED,
            user_id="u",
            task={"source": "user", "content": "hi"},
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        session.add(
            Message(
                created_at=datetime(2026, 6, 8, 19, 22, 16, 95839),
                updated_at=datetime(2026, 6, 8, 19, 22, 16, 95917),
                session_id=parent.id,
                run_id=run.id,
                config={"source": "user", "content": "hi"},
            )
        )
        session.commit()
        return session.exec(select(Message)).one()


def test_message_datetime_serializes_to_utc_iso(db: DatabaseManager) -> None:
    msg = _seed_message(db)

    dumped = msg.model_dump(mode="json")
    assert dumped["created_at"] == "2026-06-08T19:22:16.095839+00:00"
    assert dumped["updated_at"] == "2026-06-08T19:22:16.095917+00:00"


def test_message_datetime_survives_fastapi_encoder(db: DatabaseManager) -> None:
    # The reload route passes raw model instances through jsonable_encoder.
    msg = _seed_message(db)

    enc = jsonable_encoder(msg)
    assert enc["created_at"] == "2026-06-08T19:22:16.095839+00:00"
    parsed = datetime.fromisoformat(enc["created_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_python_mode_dump_keeps_datetime_objects(db: DatabaseManager) -> None:
    # db_manager.upsert copies fields via python-mode model_dump() back onto the
    # persisted row. The serializer must NOT stringify datetimes there
    # (when_used="json"), or the round-trip writes a string into a DateTime
    # column and the upsert fails — silently dropping run status updates.
    msg = _seed_message(db)

    dumped = msg.model_dump()  # python mode
    assert isinstance(dumped["created_at"], datetime)
    assert isinstance(dumped["updated_at"], datetime)


def _seed_session(db: DatabaseManager) -> int:
    with DBSession(db.engine) as session:
        parent = Session(user_id="u", name="t")
        session.add(parent)
        session.commit()
        session.refresh(parent)
        return parent.id


def test_upsert_preserves_run_status(db: DatabaseManager) -> None:
    session_id = _seed_session(db)
    run = Run(
        session_id=session_id,
        status=RunStatus.CREATED,
        user_id="u",
        task={"source": "user", "content": "hi"},
    )
    db.upsert(run)
    run_id = run.id

    run.status = RunStatus.ACTIVE
    resp = db.upsert(run)
    assert resp.status is True

    with DBSession(db.engine) as session:
        reloaded = session.exec(select(Run).where(Run.id == run_id)).one()
        assert reloaded.status == RunStatus.ACTIVE
        assert isinstance(reloaded.created_at, datetime)


def test_upsert_returns_utc_iso_datetimes(db: DatabaseManager) -> None:
    # upsert returns data in JSON mode, so its datetimes carry UTC tzinfo.
    session_id = _seed_session(db)
    run = Run(
        session_id=session_id,
        status=RunStatus.CREATED,
        user_id="u",
        task={"source": "user", "content": "hi"},
    )
    resp = db.upsert(run)

    created = resp.data["created_at"]
    assert isinstance(created, str)
    assert datetime.fromisoformat(created).tzinfo is not None
