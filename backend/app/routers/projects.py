from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, ensure_user_workspace, get_current_user, require_owned_record
from app.models.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import project_service

router = APIRouter()


@router.get("/me", response_model=list[ProjectResponse])
def fetch_my_projects(user: CurrentUser = Depends(get_current_user)):
    return project_service.get_projects_for_user(user.id)


@router.post("", response_model=ProjectResponse)
def create_project(
    data: ProjectCreate,
    user: CurrentUser = Depends(get_current_user),
):
    setup = ensure_user_workspace(user)
    try:
        return project_service.create_project(user.id, setup.get("workspace_id"), data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {exc}")


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_record("projects", project_id, user)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        result = project_service.update_project(project_id, user.id, updates)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {exc}")
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result
