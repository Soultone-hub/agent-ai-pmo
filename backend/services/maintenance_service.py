"""
maintenance_service.py — Tâches de maintenance / conformité RGPD.

Purge **définitive** des comptes archivés (suppression douce) au-delà de la
fenêtre de rétention (90 jours par défaut). La suppression d'un `User` cascade
en base (projets → documents → analyses → chat, via `ON DELETE CASCADE`) ;
on nettoie en plus les collections vectorielles ChromaDB des projets concernés
(qui ne sont pas stockées dans PostgreSQL).
"""

import logging
import datetime

from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.project import Project

logger = logging.getLogger(__name__)


def purge_archived_users(db: Session, retention_days: int = 90) -> dict:
    """
    Supprime définitivement les comptes dont `archived_at` dépasse la rétention.

    Parameters
    ----------
    db : Session
    retention_days : int
        Nombre de jours après archivage avant suppression définitive.

    Returns
    -------
    dict
        Récapitulatif : {"users", "projects", "collections"} supprimés.
    """
    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)

    users = db.query(User).filter(
        User.archived_at.isnot(None),
        User.archived_at < cutoff,
    ).all()

    if not users:
        logger.info("Purge RGPD : aucun compte archivé > %d j à supprimer.", retention_days)
        return {"users": 0, "projects": 0, "collections": 0}

    # Récupérer les project_id AVANT suppression (pour nettoyer ChromaDB ensuite)
    user_ids = [u.id for u in users]
    project_ids = [
        str(pid)
        for (pid,) in db.query(Project.id).filter(Project.owner_id.in_(user_ids)).all()
    ]

    # Suppression des comptes → cascade SQL sur projets/documents/analyses/chat
    for u in users:
        db.delete(u)
    db.commit()

    # Nettoyage des collections vectorielles orphelines
    collections_deleted = 0
    for pid in project_ids:
        try:
            from backend.services.rag_service import delete_project_collection
            if delete_project_collection(pid):
                collections_deleted += 1
        except Exception as e:
            logger.warning("Purge RGPD : échec nettoyage collection projet %s : %s", pid, e)

    logger.info(
        "Purge RGPD : %d compte(s), %d projet(s), %d collection(s) supprimés (rétention %d j).",
        len(users), len(project_ids), collections_deleted, retention_days,
    )
    return {"users": len(users), "projects": len(project_ids), "collections": collections_deleted}
