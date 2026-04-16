import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database.db import get_db
from backend.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Projets"])


class CreateProjectRequest(BaseModel):
    name: str
    owner_id: str


@router.post("/")
def create_project(request: CreateProjectRequest, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        owner_id=request.owner_id,
        name=request.name,
        status="active"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {
        "id": str(project.id),
        "name": project.name,
        "status": project.status,
        "created_at": str(project.created_at)
    }


@router.get("/")
def list_projects(owner_id: str, db: Session = Depends(get_db)):
    projects = db.query(Project).filter(
        Project.owner_id == owner_id,
        Project.status == "active"
    ).order_by(Project.created_at.desc()).all()
    return {
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "status": p.status,
                "created_at": str(p.created_at)
            }
            for p in projects
        ]
    }


@router.patch("/{project_id}")
def rename_project(project_id: str, request: CreateProjectRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    project.name = request.name
    db.commit()
    return {"id": str(project.id), "name": project.name}


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    project.status = "archived"
    db.commit()
    return {"message": f"Projet '{project.name}' archivé."}