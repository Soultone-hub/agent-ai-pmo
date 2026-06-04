import unicodedata
from urllib.parse import quote
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.models.analysis import Analysis
from backend.models.project import Project
from backend.models.user import User
from backend.services.auth_service import get_current_user
from backend.services import export_service

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _is_real_analysis(analysis: Analysis) -> bool:
    """Écarte les sous-enregistrements générés lors des analyses multi-documents."""
    data = analysis.result_json or {}
    return "parent_analysis_id" not in data


def _export_response(analysis: Analysis, project: Project, fmt: str) -> Response:
    """Construit la réponse HTTP de téléchargement pour une analyse donnée."""
    try:
        content, media_type, filename = export_service.build_export(
            analysis_type=analysis.analysis_type,
            result=analysis.result_json,
            project_name=project.name if project else "Projet",
            created_at=analysis.created_at,
            fmt=fmt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Content-Disposition compatible accents (RFC 5987 + repli ASCII)
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode() or "export"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@router.get("/project/{project_id}")
def list_project_analyses(
    project_id: str,
    type: str = Query(default="document", description="Type d'analyse : document, risks, kpi, copil"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste toutes les analyses d'un projet, filtrées par type, avec résumé."""
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == type,
    ).order_by(Analysis.created_at.desc()).all()

    def _summarize(a) -> dict[str, Any]:
        r = a.result_json or {}
        entry: dict[str, Any] = {
            "id": str(a.id),
            "created_at": str(a.created_at),
        }
        if type == "document":
            entry["nb_objectifs"]      = len(r.get("objectifs") or [])
            entry["nb_contraintes"]    = len(r.get("contraintes") or [])
            entry["nb_points_cles"]    = len(r.get("points_cles") or [])
            entry["resume"]            = (r.get("resume") or "")[:120]
        elif type == "risks":
            risks = r.get("risks") or []
            entry["nb_risques"]        = len(risks)
            entry["nb_critiques"]      = sum(1 for x in risks if (x or {}).get("niveau") == "critique")
            entry["resume"]            = (r.get("resume") or "")[:120]
        elif type == "kpi":
            entry["nb_kpis"]           = len(r.get("kpis") or [])
            entry["score_global"]      = (r.get("score_global") or {}).get("valeur", 0)
        elif type == "copil":
            entry["resume_executif"]   = (r.get("resume_executif") or "")[:120]
        return entry

    return {
        "total": len(analyses),
        "historique": [_summarize(a) for a in analyses],
    }


@router.get("/project/{project_id}/latest")
def get_latest_analysis(
    project_id: str,
    type: str = Query(default="document"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne la dernière analyse d'un projet pour un type donné."""
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == type,
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse trouvée")

    return {
        "id": str(analysis.id),
        "type": analysis.analysis_type,
        "created_at": str(analysis.created_at),
        "result": analysis.result_json,
    }


@router.get("/project/{project_id}/export")
def export_latest_analysis(
    project_id: str,
    type: str = Query(default="document", description="Type d'analyse : document, risks, kpi, copil"),
    format: str = Query(default="pdf", description="Format d'export : pdf, docx, xlsx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporte la dernière analyse réelle d'un projet (PDF / Word / Excel)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Projet non trouvé")

    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == type,
    ).order_by(Analysis.created_at.desc()).all()

    analysis = next((a for a in analyses if _is_real_analysis(a)), None)
    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse à exporter")

    return _export_response(analysis, project, format)


@router.get("/{analysis_id}/export")
def export_analysis(
    analysis_id: str,
    format: str = Query(default="pdf", description="Format d'export : pdf, docx, xlsx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exporte une analyse précise par son ID (PDF / Word / Excel)."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analyse non trouvée")

    project = db.query(Project).filter(Project.id == analysis.project_id).first()
    if not project or str(project.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès refusé")

    return _export_response(analysis, project, format)


@router.get("/{analysis_id}")
def get_analysis_by_id(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Charge le résultat complet d'une analyse spécifique par son ID."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analyse non trouvée")

    return {
        "id": str(analysis.id),
        "type": analysis.analysis_type,
        "created_at": str(analysis.created_at),
        "result": analysis.result_json,
    }
