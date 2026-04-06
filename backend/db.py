from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine  # pyright: ignore[reportMissingImports]
from sqlalchemy.engine import Connection  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session, sessionmaker  # pyright: ignore[reportMissingImports]

from .repositories import TelemetryRepository
from .repositories import AlertsRepository
from .repositories import ChargerRepository
from .repositories import ConsumptionIntelligenceRepository
from .repositories import ProductionIntelligenceRepository
from . import settings
from .observability import bind_db_engine_metrics


def _engine_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {}
    kwargs["pool_pre_ping"] = True
    kwargs["future"] = True
    if settings.DATABASE_DSN.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.DATABASE_DSN, **_engine_kwargs())
bind_db_engine_metrics(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_connection() -> Iterator[Connection]:
    with engine.connect() as connection:
        yield connection


def get_telemetry_repository(executor: Session | Connection) -> TelemetryRepository:
    return TelemetryRepository(executor=executor, dialect_name=engine.dialect.name)


def get_production_intelligence_repository(executor: Session | Connection) -> ProductionIntelligenceRepository:
    return ProductionIntelligenceRepository(executor=executor)


def get_consumption_intelligence_repository(executor: Session | Connection) -> ConsumptionIntelligenceRepository:
    return ConsumptionIntelligenceRepository(executor=executor)


def get_alerts_repository(executor: Session | Connection) -> AlertsRepository:
    return AlertsRepository(executor=executor)


def get_charger_repository(executor: Session | Connection) -> ChargerRepository:
    return ChargerRepository(executor=executor, dialect_name=engine.dialect.name)
