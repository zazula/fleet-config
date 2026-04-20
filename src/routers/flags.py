from __future__ import annotations

import hashlib
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models.feature_flag import FeatureFlag

router = APIRouter(prefix="/api/v1/flags", tags=["flags"])


class FeatureFlagCreate(BaseModel):
    name: str
    enabled: bool
    rollout_pct: float = Field(ge=0, le=100)
    rules: dict[str, Any] | None = None


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    rollout_pct: float | None = Field(default=None, ge=0, le=100)
    rules: dict[str, Any] | None = None

    @field_validator("rules")
    @classmethod
    def preserve_nullable_rules(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return value


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    enabled: bool
    rollout_pct: float
    rules: dict[str, Any] | None


class FlagEvaluationRequest(BaseModel):
    agent_id: str
    context: dict[str, Any]


class FlagEvaluationResponse(BaseModel):
    name: str
    enabled: bool
    reason: str


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_flag(db: Session, name: str) -> FeatureFlag | None:
    return db.scalar(select(FeatureFlag).where(FeatureFlag.name == name))


def evaluate_flag(flag: FeatureFlag, agent_id: str) -> tuple[bool, str]:
    if not flag.enabled:
        return False, "flag disabled"
    if flag.rollout_pct == 100:
        return True, "full rollout"
    if flag.rollout_pct == 0:
        return False, "zero rollout"

    digest = hashlib.sha256(f"{agent_id}{flag.name}".encode()).hexdigest()
    bucket = int(digest, 16) % 100
    enabled = bucket < flag.rollout_pct
    return enabled, f"agent bucket {bucket} compared to rollout {flag.rollout_pct}"


@router.post("", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
def create_flag(payload: FeatureFlagCreate, db: Session = Depends(get_db)) -> FeatureFlagResponse:
    existing = get_flag(db, payload.name)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Flag already exists")

    flag = FeatureFlag(
        name=payload.name,
        enabled=payload.enabled,
        rollout_pct=payload.rollout_pct,
        rules=payload.rules,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.get("/{name}", response_model=FeatureFlagResponse)
def read_flag(name: str, db: Session = Depends(get_db)) -> FeatureFlagResponse:
    flag = get_flag(db, name)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
    return FeatureFlagResponse.model_validate(flag)


@router.put("/{name}", response_model=FeatureFlagResponse)
def update_flag(
    name: str,
    payload: FeatureFlagUpdate,
    db: Session = Depends(get_db),
) -> FeatureFlagResponse:
    flag = get_flag(db, name)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(flag, field_name, value)

    db.add(flag)
    db.commit()
    db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.delete("/{name}", response_model=FeatureFlagResponse)
def delete_flag(name: str, db: Session = Depends(get_db)) -> FeatureFlagResponse:
    flag = get_flag(db, name)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")

    flag.enabled = False
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.post("/{name}/evaluate", response_model=FlagEvaluationResponse)
def evaluate_flag_endpoint(
    name: str,
    payload: FlagEvaluationRequest,
    db: Session = Depends(get_db),
) -> FlagEvaluationResponse:
    flag = get_flag(db, name)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")

    enabled, reason = evaluate_flag(flag, payload.agent_id)
    return FlagEvaluationResponse(name=flag.name, enabled=enabled, reason=reason)
