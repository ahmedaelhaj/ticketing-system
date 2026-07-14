from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, Ticket, TicketComment, TicketStatusHistory, Approval, UserRole, TicketStatus, TicketPriority
from app.schemas.schemas import (
    TicketCreate, TicketOut, TicketUpdateStatus, TicketRedirect, CommentCreate, CommentOut,
    TicketStatusHistoryOut, ApprovalOut,
)
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_visible_ticket(db: Session, actor: User, ticket_id: str) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if not ticket_service.can_view_ticket(actor, ticket):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this ticket")
    return ticket


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = ticket_service.create_ticket(
        db, user, payload.title, payload.description, payload.priority,
        payload.assigned_to, payload.target_team_id, payload.requested_assigned_to,
    )
    return ticket_service.enrich_ticket(db, ticket)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    priority: Optional[TicketPriority] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    query = ticket_service.visible_tickets_query(db, user)

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority:
        query = query.filter(Ticket.priority == priority)

    # team_id / user_id filters only meaningful (and permitted) for team_admin / super_admin
    if team_id and user.role in (UserRole.super_admin,):
        query = query.filter(Ticket.team_id == team_id)
    if user_id and user.role in (UserRole.team_admin, UserRole.super_admin):
        query = query.filter((Ticket.created_by == user_id) | (Ticket.assigned_to == user_id))

    tickets = query.order_by(Ticket.created_at.desc()).all()
    return [ticket_service.enrich_ticket(db, t) for t in tickets]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = _get_visible_ticket(db, user, ticket_id)
    return ticket_service.enrich_ticket(db, ticket)


@router.get("/{ticket_id}/history", response_model=list[TicketStatusHistoryOut])
def ticket_history(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)
    entries = db.query(TicketStatusHistory).filter(TicketStatusHistory.ticket_id == ticket_id) \
        .order_by(TicketStatusHistory.changed_at.asc()).all()
    return [ticket_service.enrich_history(db, e) for e in entries]


@router.get("/{ticket_id}/approvals", response_model=list[ApprovalOut])
def ticket_approvals(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)
    approvals = db.query(Approval).filter(Approval.ticket_id == ticket_id) \
        .order_by(Approval.created_at.asc()).all()
    return [ticket_service.enrich_approval(db, a) for a in approvals]


@router.patch("/{ticket_id}/status", response_model=TicketOut)
def update_status(ticket_id: str, payload: TicketUpdateStatus, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    ticket = ticket_service.update_status(db, user, ticket, payload.status)
    return ticket_service.enrich_ticket(db, ticket)


@router.post("/{ticket_id}/redirect", response_model=TicketOut)
def redirect_ticket(ticket_id: str, payload: TicketRedirect, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    ticket = ticket_service.redirect_ticket(db, user, ticket, payload.assigned_to, payload.team_id)
    return ticket_service.enrich_ticket(db, ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if not ticket_service.can_delete_ticket(user, ticket):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only delete your own ticket before it's been approved (pending approval or rejected). "
            "A super admin can delete any ticket."
        )
    db.delete(ticket)
    db.commit()


def _enrich_comment(db: Session, c: TicketComment) -> CommentOut:
    out = CommentOut.model_validate(c)
    out.author_name = ticket_service._user_name(db, c.author_id)
    return out


@router.get("/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id) \
        .order_by(TicketComment.created_at.asc()).all()
    return [_enrich_comment(db, c) for c in comments]


@router.post("/{ticket_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(ticket_id: str, payload: CommentCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)
    comment = TicketComment(ticket_id=ticket_id, author_id=user.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _enrich_comment(db, comment)
