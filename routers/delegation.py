"""Delegation of authority + append-only benchmark audit trail (Q15).

Demo-simulated: delegation records another officer as a reviewer for a
benchmark run, and every action (benchmark created, delegated, approved /
rejected) is appended to a per-run audit log so the decision trail is
reproducible — a requirement for procurement records.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, select

from database import BenchmarkAuditLog, DelegationRecord, async_session_maker
from routers.auth_routes import require_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["delegation"])


class DelegationCreate(BaseModel):
    search_id: str = Field(min_length=1)
    delegate_to_name: str = Field(min_length=1, max_length=200)
    delegate_to_email: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=1000)


class DelegationResolve(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=1000)


def _actor_name(user) -> str | None:
    if user is None:
        return None
    return user.name or user.email


def _actor_email(user) -> str | None:
    if user is None:
        return None
    return user.email


async def append_audit(
    session,
    search_id: str,
    action: str,
    actor_name: str | None,
    note: str | None = None,
) -> None:
    """Insert an append-only audit log entry for a benchmark run."""
    entry = BenchmarkAuditLog(
        search_id=search_id,
        action=action,
        actor_name=actor_name,
        note=note,
    )
    session.add(entry)
    await session.commit()


@router.post("/delegations")
async def create_delegation(
    req: DelegationCreate,
    user=Depends(require_current_user),
):
    """Delegate a benchmark for review to another officer (demo-simulated)."""
    async with async_session_maker() as session:
        delegation = DelegationRecord(
            search_id=req.search_id,
            delegated_by_name=_actor_name(user),
            delegated_by_email=_actor_email(user),
            delegate_to_name=req.delegate_to_name,
            delegate_to_email=req.delegate_to_email,
            note=req.note,
            status="open",
        )
        session.add(delegation)
        await session.flush()

        await append_audit(
            session,
            req.search_id,
            "delegated_for_review",
            _actor_name(user),
            note=f"Delegated to {req.delegate_to_name} for review"
            + (f": {req.note}" if req.note else ""),
        )

        await session.refresh(delegation)
        return {
            "id": delegation.id,
            "search_id": delegation.search_id,
            "delegated_by_name": delegation.delegated_by_name,
            "delegate_to_name": delegation.delegate_to_name,
            "delegate_to_email": delegation.delegate_to_email,
            "note": delegation.note,
            "status": delegation.status,
            "decision": delegation.decision,
            "decision_note": delegation.decision_note,
            "created_at": delegation.created_at,
            "completed_at": delegation.completed_at,
        }


@router.get("/delegations")
async def list_delegations(
    search_id: str,
    user=Depends(require_current_user),
):
    """List delegations attached to a benchmark run."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(DelegationRecord)
            .where(DelegationRecord.search_id == search_id)
            .order_by(desc(DelegationRecord.created_at))
        )
        rows = result.scalars().all()
        return [
            {
                "id": d.id,
                "search_id": d.search_id,
                "delegated_by_name": d.delegated_by_name,
                "delegate_to_name": d.delegate_to_name,
                "delegate_to_email": d.delegate_to_email,
                "note": d.note,
                "status": d.status,
                "decision": d.decision,
                "decision_note": d.decision_note,
                "created_at": d.created_at,
                "completed_at": d.completed_at,
            }
            for d in rows
        ]


@router.post("/delegations/{delegation_id}/resolve")
async def resolve_delegation(
    delegation_id: str,
    req: DelegationResolve,
    user=Depends(require_current_user),
):
    """Record a reviewer's approve/reject decision on a delegation."""
    async with async_session_maker() as session:
        delegation = await session.get(DelegationRecord, delegation_id)
        if delegation is None:
            raise HTTPException(status_code=404, detail="Delegation not found")
        if delegation.status != "open":
            raise HTTPException(
                status_code=409,
                detail=f"Delegation already {delegation.status}",
            )

        delegation.status = "completed"
        delegation.decision = req.decision
        delegation.decision_note = req.note
        delegation.completed_at = datetime.now(timezone.utc)
        await session.flush()

        await append_audit(
            session,
            delegation.search_id,
            f"review_{req.decision}",
            _actor_name(user),
            note=f"Delegation from {delegation.delegate_to_name}"
            + (f": {req.note}" if req.note else ""),
        )

        return {
            "id": delegation.id,
            "status": delegation.status,
            "decision": delegation.decision,
        }


@router.get("/audit")
async def get_audit(
    search_id: str,
    user=Depends(require_current_user),
):
    """Append-only action trail for a benchmark run."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BenchmarkAuditLog)
            .where(BenchmarkAuditLog.search_id == search_id)
            .order_by(asc(BenchmarkAuditLog.created_at))
        )
        rows = result.scalars().all()
        return [
            {
                "id": e.id,
                "search_id": e.search_id,
                "action": e.action,
                "actor_name": e.actor_name,
                "note": e.note,
                "created_at": e.created_at,
            }
            for e in rows
        ]