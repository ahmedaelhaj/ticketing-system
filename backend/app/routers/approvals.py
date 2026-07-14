from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_team_admin_or_above
from app.models import User, Approval, ApprovalDecision, UserRole
from app.schemas.schemas import ApprovalOut, ApprovalDecisionRequest
from app.services import ticket_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/pending", response_model=list[ApprovalOut])
def pending_approvals(db: Session = Depends(get_db), user: User = Depends(require_team_admin_or_above)):
    query = db.query(Approval).filter(Approval.decision == ApprovalDecision.pending)
    if user.role == UserRole.team_admin:
        query = query.filter(Approval.approver_id == user.id)
    # super_admin sees every pending approval, across all teams, as an override queue
    approvals = query.order_by(Approval.created_at.asc()).all()
    return [ticket_service.enrich_approval(db, a) for a in approvals]


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
def decide(approval_id: str, payload: ApprovalDecisionRequest, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval not found")
    approval = ticket_service.decide_approval(
        db, user, approval, payload.decision, payload.comment, payload.assigned_to
    )
    return ticket_service.enrich_approval(db, approval)
