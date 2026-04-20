from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models.config_key import ConfigKey

router = APIRouter(prefix="/api/v1/configs", tags=["configs"])


class ConfigCreate(BaseModel):
    namespace: str
    key: str
    value: Any


class ConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    namespace: str
    key: str
    value: Any
    version: int


class ConfigUpdate(BaseModel):
    value: Any


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_active_config(db: Session, namespace: str, key: str) -> ConfigKey | None:
    statement = select(ConfigKey).where(
        ConfigKey.namespace == namespace,
        ConfigKey.key == key,
        ConfigKey.is_active.is_(True),
    )
    return db.scalar(statement)


@router.post("", response_model=ConfigResponse, status_code=status.HTTP_201_CREATED)
def create_config(payload: ConfigCreate, db: Session = Depends(get_db)) -> ConfigResponse:
    existing = db.scalar(
        select(ConfigKey).where(
            ConfigKey.namespace == payload.namespace,
            ConfigKey.key == payload.key,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config already exists")

    config = ConfigKey(namespace=payload.namespace, key=payload.key, value=payload.value, version=1)
    db.add(config)
    db.commit()
    db.refresh(config)
    return ConfigResponse.model_validate(config)


@router.get("/{namespace}/{key}", response_model=ConfigResponse)
def read_config(namespace: str, key: str, db: Session = Depends(get_db)) -> ConfigResponse:
    config = get_active_config(db, namespace, key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return ConfigResponse.model_validate(config)


@router.get("", response_model=list[ConfigResponse])
def list_configs(namespace: str | None = None, db: Session = Depends(get_db)) -> list[ConfigResponse]:
    statement = select(ConfigKey).where(ConfigKey.is_active.is_(True))
    if namespace is not None:
        statement = statement.where(ConfigKey.namespace == namespace)
    statement = statement.order_by(ConfigKey.namespace.asc(), ConfigKey.key.asc())
    configs = db.scalars(statement).all()
    return [ConfigResponse.model_validate(config) for config in configs]


@router.put("/{namespace}/{key}", response_model=ConfigResponse)
def update_config(
    namespace: str,
    key: str,
    payload: ConfigUpdate,
    db: Session = Depends(get_db),
) -> ConfigResponse:
    config = get_active_config(db, namespace, key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    config.value = payload.value
    config.version += 1
    db.add(config)
    db.commit()
    db.refresh(config)
    return ConfigResponse.model_validate(config)


@router.delete("/{namespace}/{key}", response_model=ConfigResponse)
def delete_config(namespace: str, key: str, db: Session = Depends(get_db)) -> ConfigResponse:
    config = get_active_config(db, namespace, key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    config.is_active = False
    db.add(config)
    db.commit()
    db.refresh(config)
    return ConfigResponse.model_validate(config)
