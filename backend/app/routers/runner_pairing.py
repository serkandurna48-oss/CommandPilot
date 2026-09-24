from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_browser_user, get_current_user
from app.models.runner import (
    RunnerConnectionResponse,
    RunnerPairingApprove,
    RunnerPairingPoll,
    RunnerPairingRequestCreate,
    RunnerPairingRequestResponse,
    RunnerPairingStatusResponse,
)
from app.services import runner_connection_service

router = APIRouter()


# ── Unauthenticated — called by the runner itself, which has no session ────
@router.post("/pairing/request", response_model=RunnerPairingRequestResponse)
def request_pairing(data: RunnerPairingRequestCreate):
    return runner_connection_service.create_pairing_request(data.label)


@router.post("/pairing/poll", response_model=RunnerPairingStatusResponse)
def poll_pairing(data: RunnerPairingPoll):
    # Body, not a query param — a user_code is short-lived and low-value
    # compared to the actual runner_token, but it's still pairing material
    # that has no business showing up in a URL or access log.
    return {"status": runner_connection_service.poll_pairing_status(data.user_code)}


# ── Authenticated — called from the logged-in browser session ─────────────
@router.post("/pairing/approve", response_model=RunnerConnectionResponse)
def approve_pairing(data: RunnerPairingApprove, user: CurrentUser = Depends(get_current_browser_user)):
    setup = ensure_user_workspace(user)
    connection = runner_connection_service.approve_pairing(
        user.id, setup.get("workspace_id"), data.user_code, data.label
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Code unbekannt oder abgelaufen. Neuen Code im Runner erzeugen.")
    return connection


@router.get("", response_model=list[RunnerConnectionResponse])
def list_connections(user: CurrentUser = Depends(get_current_user)):
    return runner_connection_service.list_connections_for_user(user.id)


@router.post("/{connection_id}/revoke", response_model=dict)
def revoke_connection(connection_id: str, user: CurrentUser = Depends(get_current_user)):
    ok = runner_connection_service.revoke_connection(user.id, connection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"revoked": True}
