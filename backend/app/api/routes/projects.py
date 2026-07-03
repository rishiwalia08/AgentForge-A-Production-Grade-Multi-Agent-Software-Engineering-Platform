from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, DatabaseRepository
from app.core.auth import get_current_user
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> ProjectResponse:
    project = DatabaseRepository.create_project(
        db,
        user_id=current_user["id"],
        name=payload.name,
        description=payload.description,
        repo_path=payload.repo_path
    )
    return project

@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> list[ProjectResponse]:
    return DatabaseRepository.list_projects(db, user_id=current_user["id"])

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> None:
    project = DatabaseRepository.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target project not found."
        )
    if project.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access permission for this project."
        )
    
    DatabaseRepository.delete_project(db, project_id)
