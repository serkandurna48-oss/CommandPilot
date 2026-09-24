from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.services import vault_service

router = APIRouter()


# One chosen data source (24.09.2026 — MVP data-source visibility pass): the
# Vault, not Calendar/Notion. Vault notes already have a real, pre-existing
# per-project association (file naming convention under Projekte/) — Calendar
# events and Notion tasks have no project linkage at all, and inventing one
# would repeat the exact mistake work_orders_context_service.py's docstring
# already warns against. Vault is also the one source with zero external
# API/auth surface (local filesystem only), so this is the smallest-risk way
# to give the Home dashboard a real "is my second brain actually reachable
# right now" signal instead of none at all.
@router.get("/vault-status")
def vault_status(user: CurrentUser = Depends(get_current_user)):
    return vault_service.get_vault_status(user.id)
