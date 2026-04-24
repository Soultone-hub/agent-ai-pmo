from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.models.analysis import Analysis
from backend.models.user import User
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


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
