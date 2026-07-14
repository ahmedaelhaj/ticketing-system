from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Ticket, TicketStatus, TicketStatusHistory, Notification, User, UserRole
from app.services.ticket_service import team_admin_of

# Tickets open/in-progress longer than this are flagged as overdue
OVERDUE_THRESHOLD_HOURS = 72

# Tickets stuck awaiting approval longer than this get a reminder to the approver
PENDING_APPROVAL_REMINDER_HOURS = 24
# ...and if STILL pending after this much longer on top of that, super admin gets escalated
PENDING_APPROVAL_ESCALATION_HOURS = 72

# Don't re-notify more often than this for the same ticket/reason
REMINDER_COOLDOWN_HOURS = 24


def _recently_reminded(db, ticket_id: str, marker: str) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=REMINDER_COOLDOWN_HOURS)
    return db.query(TicketStatusHistory).filter(
        TicketStatusHistory.ticket_id == ticket_id,
        TicketStatusHistory.changed_at >= cutoff,
        TicketStatusHistory.note.ilike(f"%{marker}%"),
    ).first() is not None


def _log_note(db, ticket: Ticket, note: str, actor_id: str | None = None):
    """SLA notes use the ticket's own current status for both from/to (nothing
    actually changes state) so they show up inline in the unified timeline
    without looking like a real transition."""
    db.add(TicketStatusHistory(
        ticket_id=ticket.id,
        from_status=ticket.status,
        to_status=ticket.status,
        changed_by=actor_id or ticket.created_by,
        note=note,
    ))


@celery_app.task(name="app.tasks.check_overdue_tickets")
def check_overdue_tickets():
    """Runs daily via celery beat. Flags stale tickets and reminds/escalates
    approvals that have been sitting too long."""
    db = SessionLocal()
    try:
        flagged_active = 0
        flagged_pending = 0
        escalated = 0

        # --- Open / in-progress tickets with no recent activity ---
        active_cutoff = datetime.utcnow() - timedelta(hours=OVERDUE_THRESHOLD_HOURS)
        stale = db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress]),
            Ticket.updated_at < active_cutoff,
        ).all()

        for ticket in stale:
            marker = "SLA reminder: no activity"
            if _recently_reminded(db, ticket.id, marker):
                continue
            if ticket.assigned_to:
                db.add(Notification(
                    user_id=ticket.assigned_to,
                    type="sla_overdue",
                    message=f"Ticket '{ticket.title}' has had no activity in over "
                            f"{OVERDUE_THRESHOLD_HOURS} hours.",
                ))
            _log_note(db, ticket, f"{marker} for over {OVERDUE_THRESHOLD_HOURS}h — reminder sent to assignee.")
            flagged_active += 1

        # --- Tickets stuck in pending_approval too long ---
        reminder_cutoff = datetime.utcnow() - timedelta(hours=PENDING_APPROVAL_REMINDER_HOURS)
        escalation_cutoff = datetime.utcnow() - timedelta(
            hours=PENDING_APPROVAL_REMINDER_HOURS + PENDING_APPROVAL_ESCALATION_HOURS
        )
        pending = db.query(Ticket).filter(
            Ticket.status == TicketStatus.pending_approval,
            Ticket.updated_at < reminder_cutoff,
        ).all()

        for ticket in pending:
            from app.services.ticket_service import current_pending_approval
            approval = current_pending_approval(db, ticket.id)
            approver = db.query(User).filter(User.id == approval.approver_id).first() if approval else None

            is_severely_overdue = ticket.updated_at < escalation_cutoff
            marker = "SLA escalation" if is_severely_overdue else "SLA reminder: approval pending"
            if _recently_reminded(db, ticket.id, marker):
                continue

            if is_severely_overdue:
                super_admins = db.query(User).filter(User.role == UserRole.super_admin, User.is_active == True).all()
                for sa in super_admins:
                    db.add(Notification(
                        user_id=sa.id,
                        type="sla_escalation",
                        message=f"Ticket '{ticket.title}' has been awaiting approval from "
                                f"{approver.full_name if approver else 'its approver'} for over "
                                f"{PENDING_APPROVAL_REMINDER_HOURS + PENDING_APPROVAL_ESCALATION_HOURS} hours. "
                                f"You can approve it directly from the Approvals page.",
                    ))
                _log_note(db, ticket,
                          f"{marker}: no decision after "
                          f"{PENDING_APPROVAL_REMINDER_HOURS + PENDING_APPROVAL_ESCALATION_HOURS}h — escalated to super admin.")
                escalated += 1
            else:
                if approver:
                    db.add(Notification(
                        user_id=approver.id,
                        type="sla_reminder",
                        message=f"Ticket '{ticket.title}' has been awaiting your approval for over "
                                f"{PENDING_APPROVAL_REMINDER_HOURS} hours.",
                    ))
                _log_note(db, ticket, f"{marker} for over {PENDING_APPROVAL_REMINDER_HOURS}h.")
                flagged_pending += 1

        db.commit()
        return {"flagged_active": flagged_active, "flagged_pending": flagged_pending, "escalated": escalated}
    finally:
        db.close()


@celery_app.task(name="app.tasks.send_notification_email")
def send_notification_email(user_email: str, subject: str, body: str):
    """Placeholder for real email delivery (SMTP/SES/SendGrid) — wire up in production."""
    print(f"[email] to={user_email} subject={subject}\n{body}")
