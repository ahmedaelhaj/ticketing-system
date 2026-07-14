from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import (
    User, Team, Ticket, Approval, TicketStatusHistory, Notification,
    UserRole, TicketStatus, ApprovalDecision,
)

# Allowed manual status transitions (pending_approval / rejected are handled separately)
ALLOWED_TRANSITIONS = {
    TicketStatus.open: [TicketStatus.in_progress],
    TicketStatus.in_progress: [TicketStatus.closed],
    TicketStatus.closed: [TicketStatus.open],       # reopen — team_admin/super_admin only
    TicketStatus.rejected: [TicketStatus.pending_approval],  # resubmit
}

REOPEN_ROLES = (UserRole.team_admin, UserRole.super_admin)


def team_admin_of(db: Session, team_id: str | None) -> User | None:
    if not team_id:
        return None
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team or not team.team_admin_id:
        return None
    return db.query(User).filter(User.id == team.team_admin_id).first()


def any_super_admin(db: Session) -> User | None:
    return db.query(User).filter(User.role == UserRole.super_admin, User.is_active == True).first()


def resolve_stage1_approver(db: Session, creator: User) -> User | None:
    """The requester's own manager in the hierarchy: a normal user's manager is
    their team admin; a team admin's manager is the super admin (never
    themselves — a team admin cannot approve their own request just because
    they happen to admin the team they belong to)."""
    if creator.role == UserRole.team_admin:
        return any_super_admin(db)
    return team_admin_of(db, creator.team_id)


def notify(db: Session, user_id: str, notif_type: str, message: str, ticket_id: str | None = None):
    if not user_id:
        return
    db.add(Notification(user_id=user_id, type=notif_type, message=message, ticket_id=ticket_id))


def log_history(db: Session, ticket: Ticket, from_status, to_status, actor: User, note: str | None = None):
    db.add(TicketStatusHistory(
        ticket_id=ticket.id,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor.id,
        note=note,
    ))


def _start_approval(db: Session, ticket: Ticket, approver: User, stage: int):
    db.add(Approval(ticket_id=ticket.id, approver_id=approver.id,
                     stage=stage, decision=ApprovalDecision.pending))


def _team_name(db: Session, team_id: str | None) -> str:
    if not team_id:
        return "no team"
    t = db.query(Team).filter(Team.id == team_id).first()
    return t.name if t else "unknown team"


def create_ticket(db: Session, creator: User, title: str, description: str | None,
                   priority, assigned_to: str | None, target_team_id: str | None,
                   requested_assigned_to: str | None = None) -> Ticket:
    """
    target_team_id lets the requester send the ticket to a different team than
    their own (e.g. Finance -> IT). If it's None or equal to the creator's own
    team, this is a same-team ticket (single-stage approval).

    requested_assigned_to is an optional hint: "please give this specifically to
    this person on the target team." The final approver can still override it.
    """
    own_team_id = creator.team_id
    cross_team = bool(target_team_id) and target_team_id != own_team_id

    ticket = Ticket(
        title=title,
        description=description,
        priority=priority,
        created_by=creator.id,
        assigned_to=None,
        team_id=own_team_id,
        origin_team_id=own_team_id,  # permanent, for audit — never changes after this
        requested_team_id=target_team_id if cross_team else None,
        requested_assigned_to=requested_assigned_to,
    )

    if creator.role == UserRole.super_admin:
        # Auto-approved, no approval chain needed. If a target team was given,
        # the ticket lands directly with that team; otherwise it has no team.
        ticket.team_id = target_team_id or own_team_id
        ticket.origin_team_id = ticket.team_id
        ticket.assigned_to = assigned_to
        ticket.status = TicketStatus.open
        db.add(ticket)
        db.flush()
        log_history(db, ticket, None, TicketStatus.open, creator, note="Created by super admin — auto-approved.")
    else:
        ticket.status = TicketStatus.pending_approval
        db.add(ticket)
        db.flush()

        # Stage 1 is always the requester's own team admin — for a same-team
        # ticket that's also the final approval; for cross-team it's just the
        # authorization step before it's handed to the target team.
        approver = resolve_stage1_approver(db, creator)
        if not approver:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No approver could be resolved for this ticket "
                + ("(no super admin exists)." if creator.role == UserRole.team_admin
                   else "(your team has no admin assigned).")
            )
        _start_approval(db, ticket, approver, stage=1)
        note = f"Created by {creator.full_name} — awaiting approval from {approver.full_name}"
        if cross_team:
            note += f" (requested for {_team_name(db, target_team_id)})"
        log_history(db, ticket, None, TicketStatus.pending_approval, creator, note=note)
        notify(db, approver.id, "approval_needed", f"New ticket '{ticket.title}' awaiting your approval", ticket.id)

    db.commit()
    db.refresh(ticket)
    return ticket


def can_view_ticket(actor: User, ticket: Ticket) -> bool:
    """Broader than can_touch_ticket: includes the requesting team permanently,
    even after the ticket has moved to another team's ownership, for audit."""
    if actor.role == UserRole.super_admin:
        return True
    if actor.role == UserRole.team_admin:
        return actor.team_id in (ticket.team_id, ticket.origin_team_id)
    if actor.role == UserRole.normal_user:
        return ticket.created_by == actor.id or ticket.assigned_to == actor.id
    return False


def can_touch_ticket(actor: User, ticket: Ticket) -> bool:
    """Narrower: only whoever currently owns the ticket can act on it (change
    status, redirect). The origin team keeps view access but not edit rights
    once the ticket has moved on to another team."""
    if actor.role == UserRole.super_admin:
        return True
    if actor.role == UserRole.team_admin:
        return ticket.team_id == actor.team_id
    if actor.role == UserRole.normal_user:
        return ticket.created_by == actor.id or ticket.assigned_to == actor.id
    return False


def can_start_progress(actor: User, ticket: Ticket) -> bool:
    """Narrower than the general 'can touch' rule: only super admin, the person
    the ticket is actually assigned to, or that team's admin can start work on
    it — NOT the original requester unless they're also the assignee."""
    if actor.role == UserRole.super_admin:
        return True
    if actor.id == ticket.assigned_to:
        return True
    if actor.role == UserRole.team_admin and actor.team_id == ticket.team_id:
        return True
    return False


def can_delete_ticket(actor: User, ticket: Ticket) -> bool:
    """Super admin can always delete. Otherwise only the original requester can
    delete their own ticket, and only while it's still pending_approval — before
    it's been decided either way (approved or rejected)."""
    if actor.role == UserRole.super_admin:
        return True
    if actor.id == ticket.created_by and ticket.status == TicketStatus.pending_approval:
        return True
    return False


def visible_tickets_query(db: Session, actor: User):
    query = db.query(Ticket)
    if actor.role == UserRole.normal_user:
        query = query.filter(or_(Ticket.created_by == actor.id, Ticket.assigned_to == actor.id))
    elif actor.role == UserRole.team_admin:
        # Both current owner AND original requester, permanently — so a team
        # admin never loses visibility into tickets their team raised, even
        # after they've moved on to (and been closed by) another team.
        query = query.filter(or_(Ticket.team_id == actor.team_id, Ticket.origin_team_id == actor.team_id))
    # super_admin: no restriction
    return query


def update_status(db: Session, actor: User, ticket: Ticket, new_status: TicketStatus) -> Ticket:
    if ticket.status == TicketStatus.pending_approval:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                             "Ticket must be approved or rejected before its status can change.")

    if not can_touch_ticket(actor, ticket):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this ticket.")

    allowed = ALLOWED_TRANSITIONS.get(ticket.status, [])
    if new_status not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"Cannot transition from {ticket.status.value} to {new_status.value}.")

    if ticket.status == TicketStatus.closed and new_status == TicketStatus.open:
        if actor.role not in REOPEN_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                 "Only a team admin or super admin can reopen a closed ticket.")

    if ticket.status == TicketStatus.open and new_status == TicketStatus.in_progress:
        if not can_start_progress(actor, ticket):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                 "Only the assigned user, that team's admin, or a super admin can start progress on this ticket.")

    old_status = ticket.status
    note = None

    if ticket.status == TicketStatus.rejected and new_status == TicketStatus.pending_approval:
        # Resubmission always restarts at stage 1 (the requester's own manager
        # in the hierarchy), even if the original rejection happened at stage 2.
        creator = db.query(User).filter(User.id == ticket.created_by).first()
        approver = resolve_stage1_approver(db, creator) if creator else None
        if not approver:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No approver could be resolved for resubmission.")
        if creator and creator.team_id:
            ticket.team_id = creator.team_id
        _start_approval(db, ticket, approver, stage=1)
        note = f"Resubmitted by {actor.full_name} — awaiting approval from {approver.full_name}"
        notify(db, approver.id, "approval_needed", f"Ticket '{ticket.title}' was resubmitted for your approval", ticket.id)
    elif new_status == TicketStatus.in_progress:
        note = f"Work started by {actor.full_name}"
    elif new_status == TicketStatus.closed:
        note = f"Closed by {actor.full_name}"
    elif old_status == TicketStatus.closed and new_status == TicketStatus.open:
        note = f"Reopened by {actor.full_name}"

    ticket.status = new_status
    if new_status == TicketStatus.closed:
        ticket.closed_at = datetime.utcnow()
        ticket.closed_by = actor.id
    elif new_status == TicketStatus.open and old_status == TicketStatus.closed:
        ticket.closed_at = None
        ticket.closed_by = None

    log_history(db, ticket, old_status, new_status, actor, note=note)
    db.commit()
    db.refresh(ticket)
    return ticket


def redirect_ticket(db: Session, actor: User, ticket: Ticket, new_assignee_id: str,
                     new_team_id: str | None) -> Ticket:
    if not can_touch_ticket(actor, ticket):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this ticket.")

    old_status = ticket.status
    assignee = db.query(User).filter(User.id == new_assignee_id).first()
    ticket.assigned_to = new_assignee_id
    if new_team_id and new_team_id != ticket.team_id:
        ticket.team_id = new_team_id
    ticket.requested_team_id = None

    ticket.status = TicketStatus.pending_approval

    approver = team_admin_of(db, ticket.team_id)
    if not approver:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No approver could be resolved for the new team.")

    note = (f"Redirected by {actor.full_name} to {assignee.full_name if assignee else 'a new owner'} "
            f"({_team_name(db, ticket.team_id)}) — awaiting approval from {approver.full_name}")
    log_history(db, ticket, old_status, TicketStatus.pending_approval, actor, note=note)

    _start_approval(db, ticket, approver, stage=1)
    notify(db, approver.id, "approval_needed", f"Ticket '{ticket.title}' was redirected to your team for approval", ticket.id)
    notify(db, new_assignee_id, "ticket_redirected", f"Ticket '{ticket.title}' was redirected to you", ticket.id)

    db.commit()
    db.refresh(ticket)
    return ticket


def current_pending_approval(db: Session, ticket_id: str) -> Approval | None:
    return db.query(Approval).filter(
        Approval.ticket_id == ticket_id,
        Approval.decision == ApprovalDecision.pending,
    ).order_by(Approval.created_at.desc()).first()


def decide_approval(db: Session, decider: User, approval: Approval, decision: ApprovalDecision,
                     comment: str | None, assigned_to: str | None) -> Approval:
    is_assigned_approver = approval.approver_id == decider.id
    is_super_override = decider.role == UserRole.super_admin

    if not is_assigned_approver and not is_super_override:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not the assigned approver for this ticket.")

    if approval.decision != ApprovalDecision.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "This approval has already been decided.")

    ticket = db.query(Ticket).filter(Ticket.id == approval.ticket_id).first()

    approval.decision = decision
    approval.comment = comment
    approval.decided_at = datetime.utcnow()

    old_status = ticket.status

    if decision == ApprovalDecision.reject:
        ticket.status = TicketStatus.rejected
        note = f"Rejected by {decider.full_name}" + (f": {comment}" if comment else "")
        log_history(db, ticket, old_status, ticket.status, decider, note=note)
        notify(db, ticket.created_by, "ticket_rejected",
               f"Your ticket '{ticket.title}' was rejected: {comment or 'no reason given'}", ticket.id)
        db.commit()
        db.refresh(approval)
        return approval

    # decision == approve
    is_cross_team_stage1 = bool(ticket.requested_team_id) and approval.stage == 1

    if is_cross_team_stage1:
        # Move the ticket to the target team and open a stage-2 approval there.
        # Status stays pending_approval — it's not final yet.
        target_team_id = ticket.requested_team_id
        ticket.team_id = target_team_id
        ticket.requested_team_id = None

        stage2_approver = team_admin_of(db, ticket.team_id)
        if not stage2_approver:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "The target team has no admin assigned — cannot route this ticket further."
            )
        _start_approval(db, ticket, stage2_approver, stage=2)
        note = (f"Approved by {decider.full_name} (stage 1) — forwarded to "
                f"{_team_name(db, target_team_id)} for final approval from {stage2_approver.full_name}")
        if comment:
            note += f". Note: {comment}"
        log_history(db, ticket, old_status, TicketStatus.pending_approval, decider, note=note)
        notify(db, stage2_approver.id, "approval_needed",
               f"Ticket '{ticket.title}' was routed to your team and awaits your approval", ticket.id)
        notify(db, ticket.created_by, "ticket_stage1_approved",
               f"Your ticket '{ticket.title}' was approved by your manager and sent to the target team", ticket.id)
    else:
        # Final approval — same-team ticket, or stage 2 of a cross-team ticket.
        ticket.status = TicketStatus.open
        final_assignee_id = assigned_to or ticket.requested_assigned_to or ticket.assigned_to or ticket.created_by
        ticket.assigned_to = final_assignee_id
        assignee = db.query(User).filter(User.id == final_assignee_id).first()
        note = f"Approved by {decider.full_name} — assigned to {assignee.full_name if assignee else 'requester'}"
        if comment:
            note += f". Note: {comment}"
        log_history(db, ticket, old_status, TicketStatus.open, decider, note=note)
        notify(db, ticket.created_by, "ticket_approved", f"Your ticket '{ticket.title}' was approved", ticket.id)

    db.commit()
    db.refresh(approval)
    return approval


# ---------- Enrichment helpers (attach human-readable names for API responses) ----------

def _user_name(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return u.full_name if u else None


def enrich_ticket(db: Session, ticket: Ticket):
    from app.schemas.schemas import TicketOut
    out = TicketOut.model_validate(ticket)
    out.created_by_name = _user_name(db, ticket.created_by)
    out.assigned_to_name = _user_name(db, ticket.assigned_to)
    out.requested_assigned_to_name = _user_name(db, ticket.requested_assigned_to)
    out.closed_by_name = _user_name(db, ticket.closed_by)
    out.team_name = _team_name(db, ticket.team_id) if ticket.team_id else None
    out.team_admin_name = _user_name(db, team_admin_of(db, ticket.team_id).id) if team_admin_of(db, ticket.team_id) else None
    out.origin_team_name = _team_name(db, ticket.origin_team_id) if ticket.origin_team_id else None
    out.requested_team_name = _team_name(db, ticket.requested_team_id) if ticket.requested_team_id else None
    if ticket.status == TicketStatus.pending_approval:
        current = current_pending_approval(db, ticket.id)
        out.pending_approval_stage = current.stage if current else None
    return out


def enrich_approval(db: Session, approval: Approval):
    from app.schemas.schemas import ApprovalOut
    out = ApprovalOut.model_validate(approval)
    out.approver_name = _user_name(db, approval.approver_id)

    ticket = db.query(Ticket).filter(Ticket.id == approval.ticket_id).first()
    if ticket:
        out.ticket_title = ticket.title
        out.ticket_priority = ticket.priority.value if hasattr(ticket.priority, "value") else ticket.priority
        out.requester_name = _user_name(db, ticket.created_by)
        out.team_name = _team_name(db, ticket.team_id)
        out.requested_team_name = _team_name(db, ticket.requested_team_id) if ticket.requested_team_id else None
        out.current_team_id = ticket.team_id
        out.is_final_stage = not (bool(ticket.requested_team_id) and approval.stage == 1)
    return out


def enrich_history(db: Session, entry: TicketStatusHistory):
    from app.schemas.schemas import TicketStatusHistoryOut
    out = TicketStatusHistoryOut.model_validate(entry)
    out.changed_by_name = _user_name(db, entry.changed_by)
    return out
