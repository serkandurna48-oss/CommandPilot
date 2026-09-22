from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user, require_owned_record
from app.models.work_order import (
    ActivityLogCreate,
    ActivityLogResponse,
    AgentRunCreate,
    AgentRunResponse,
    AgentRunUpdate,
    ArtifactCreate,
    ArtifactResponse,
    ReviewPackageCreate,
    ReviewPackageResponse,
    WorkOrderCreate,
    WorkOrderDetailResponse,
    WorkOrderResponse,
    WorkOrderStepCreate,
    WorkOrderStepResponse,
    WorkOrderStepUpdate,
    WorkOrderUpdate,
)
from app.services import work_order_service

router = APIRouter()


@router.post("", response_model=WorkOrderResponse)
def create_work_order(
    data: WorkOrderCreate,
    user: CurrentUser = Depends(get_current_user),
):
    setup = ensure_user_workspace(user)
    profile = setup.get("profile") or {}
    created_by = profile.get("display_name") or user.email or user.id
    try:
        return work_order_service.create_work_order(user.id, setup.get("workspace_id"), created_by, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create work order: {exc}")


@router.get("/me", response_model=list[WorkOrderResponse])
def fetch_my_work_orders(user: CurrentUser = Depends(get_current_user)):
    return work_order_service.get_work_orders_for_user(user.id)


@router.get("/{work_order_id}", response_model=WorkOrderDetailResponse)
def fetch_work_order(
    work_order_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    order = require_owned_record("work_orders", work_order_id, user)
    children = work_order_service.get_work_order_children(work_order_id)
    scope = children["approval_scope"]
    order["approval_scope_id"] = scope["id"] if scope else None
    return {**order, **children}


@router.patch("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order(
    work_order_id: str,
    data: WorkOrderUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    updates = data.model_dump(exclude_none=True)
    # daemon_run_requested_at must support being explicitly cleared to null
    # — scripts/run_work_order_daemon.py's claim signal (see migration 016)
    # PATCHes it to null before starting a run, so a crash mid-claim or a
    # later requeue never stale-retriggers. exclude_none=True above would
    # otherwise silently drop an explicit null the same way it drops "field
    # not sent at all" — model_fields_set distinguishes the two, so this
    # re-injects it only when the client actually included the key.
    if "daemon_run_requested_at" in data.model_fields_set:
        updates["daemon_run_requested_at"] = data.daemon_run_requested_at

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    status = updates.pop("status", None)
    source = updates.pop("source", None) or "ui"
    reason = updates.pop("reason", None)

    if status is None and not updates:
        # The only fields provided were source/reason with no status and no
        # other field — nothing to actually apply.
        raise HTTPException(status_code=400, detail="No fields to update")

    result = None
    if status is not None:
        # transition_work_order() (CP-OP01) is the sole authoritative state
        # machine for work_orders.status — see
        # supabase/migrations/010_transition_work_order_function.sql.
        try:
            result = work_order_service.transition_work_order(work_order_id, status, source=source, reason=reason)
        except LookupError:
            raise HTTPException(status_code=404, detail="Work order not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to transition work order: {exc}")

    if updates:
        try:
            result = work_order_service.update_work_order_fields(work_order_id, updates)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update work order: {exc}")

    if not result:
        raise HTTPException(status_code=404, detail="Work order not found")
    return result


@router.post("/{work_order_id}/activity-log", response_model=ActivityLogResponse)
def add_activity_log_entry(
    work_order_id: str,
    data: ActivityLogCreate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    try:
        return work_order_service.append_activity_log(work_order_id, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to append activity log entry: {exc}")


@router.post("/{work_order_id}/agent-runs", response_model=AgentRunResponse)
def add_agent_run(
    work_order_id: str,
    data: AgentRunCreate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    try:
        return work_order_service.create_agent_run(work_order_id, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create agent run: {exc}")


@router.patch("/{work_order_id}/agent-runs/{run_id}", response_model=AgentRunResponse)
def update_agent_run(
    work_order_id: str,
    run_id: str,
    data: AgentRunUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = work_order_service.update_agent_run(run_id, work_order_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return result


@router.post("/{work_order_id}/steps", response_model=WorkOrderStepResponse)
def add_step(
    work_order_id: str,
    data: WorkOrderStepCreate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    try:
        return work_order_service.create_step(work_order_id, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create step: {exc}")


@router.patch("/{work_order_id}/steps/{step_id}", response_model=WorkOrderStepResponse)
def update_step(
    work_order_id: str,
    step_id: str,
    data: WorkOrderStepUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = work_order_service.update_step(step_id, work_order_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Step not found")
    return result


@router.post("/{work_order_id}/artifacts", response_model=ArtifactResponse)
def add_artifact(
    work_order_id: str,
    data: ArtifactCreate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    try:
        return work_order_service.create_artifact(work_order_id, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create artifact: {exc}")


@router.put("/{work_order_id}/review-package", response_model=ReviewPackageResponse)
def upsert_review_package(
    work_order_id: str,
    data: ReviewPackageCreate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("work_orders", work_order_id, user)
    try:
        return work_order_service.upsert_review_package(work_order_id, data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save review package: {exc}")
