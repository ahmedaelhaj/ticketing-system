from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, Team, Ticket, UserRole, TicketStatus
from app.schemas.schemas import ClosePerformanceEntry, ReportSummary
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid date '{value}', expected YYYY-MM-DD")


def _scoped_query(
    db: Session, user: User, scope: str,
    team_id: Optional[str] = None, user_id: Optional[str] = None, closed_by_user_id: Optional[str] = None,
):
    """Shared scoping logic used by every report endpoint (exports AND the
    summary preview), so the two can never drift apart."""
    if scope == "mine":
        return db.query(Ticket).filter(or_(Ticket.created_by == user.id, Ticket.assigned_to == user.id))

    if scope == "team":
        target_team_id = team_id or user.team_id
        if user.role == UserRole.normal_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
        if user.role == UserRole.team_admin and user.team_id != target_team_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only report on your own team")
        if not target_team_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "team_id is required")
        # Includes both tickets currently owned by this team AND tickets this team
        # originally requested (even if now owned by another team) — full audit trail.
        return db.query(Ticket).filter(or_(Ticket.team_id == target_team_id, Ticket.origin_team_id == target_team_id))

    if scope == "global":
        if user.role != UserRole.super_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a super admin can run global reports")
        query = db.query(Ticket)
        if team_id:
            query = query.filter(or_(Ticket.team_id == team_id, Ticket.origin_team_id == team_id))
        if user_id:
            query = query.filter(or_(Ticket.created_by == user_id, Ticket.assigned_to == user_id))
        if closed_by_user_id:
            query = query.filter(Ticket.closed_by == closed_by_user_id)
        return query

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "scope must be 'mine', 'team', or 'global'")


def _apply_common_filters(query, status_filter: Optional[TicketStatus], date_from, date_to):
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if date_from:
        query = query.filter(Ticket.created_at >= date_from)
    if date_to:
        query = query.filter(Ticket.created_at < date_to + timedelta(days=1))
    return query


def _build(tickets: list[Ticket], title: str, fmt: str, subtitle: str = "") -> Response:
    if fmt == "pdf":
        content = report_service.generate_pdf(tickets, title, subtitle)
    elif fmt == "xlsx":
        content = report_service.generate_excel(tickets, title, subtitle)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "format must be 'pdf' or 'xlsx'")

    filename = f"{title.lower().replace(' ', '_')}.{fmt}"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _summarize(tickets: list[Ticket]) -> ReportSummary:
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for t in tickets:
        s = t.status.value
        p = t.priority.value
        by_status[s] = by_status.get(s, 0) + 1
        by_priority[p] = by_priority.get(p, 0) + 1
    return ReportSummary(total=len(tickets), by_status=by_status, by_priority=by_priority)


@router.get("/summary", response_model=ReportSummary)
def report_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scope: str = Query("mine"),
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    closed_by_user_id: Optional[str] = None,
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Live counts for whatever the current filter selection would export —
    lets the UI show 'this will export 42 tickets' before generating anything."""
    query = _scoped_query(db, user, scope, team_id, user_id, closed_by_user_id)
    query = _apply_common_filters(query, status_filter, _parse_date(date_from), _parse_date(date_to))
    return _summarize(query.all())


def _subtitle(status_filter, date_from, date_to) -> str:
    parts = []
    if status_filter:
        parts.append(f"status: {status_filter.value.replace('_', ' ')}")
    if date_from or date_to:
        parts.append(f"created {date_from or '…'} to {date_to or '…'}")
    return " · ".join(parts)


@router.get("/me")
def my_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    fmt: str = Query("pdf", alias="format"),
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Every ticket the current user created OR is/was assigned to — available to any role."""
    query = _scoped_query(db, user, "mine")
    query = _apply_common_filters(query, status_filter, _parse_date(date_from), _parse_date(date_to))
    return _build(query.all(), "My Ticket Report", fmt, _subtitle(status_filter, date_from, date_to))


@router.get("/team/{team_id}")
def team_report(
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    fmt: str = Query("pdf", alias="format"),
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    query = _scoped_query(db, user, "team", team_id=team_id)
    query = _apply_common_filters(query, status_filter, _parse_date(date_from), _parse_date(date_to))
    return _build(query.all(), "Team Ticket Report", fmt, _subtitle(status_filter, date_from, date_to))


@router.get("/performance", response_model=list[ClosePerformanceEntry])
def close_performance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    team_id: Optional[str] = None,
):
    """Ranked leaderboard of who has actually CLOSED tickets — this is the
    accountability view: normal users can't see it, team admins see their own
    team (audit-inclusive), super admin sees everyone and can filter by team."""
    if user.role == UserRole.normal_user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")

    query = db.query(Ticket).filter(Ticket.status == TicketStatus.closed, Ticket.closed_by.isnot(None))

    if user.role == UserRole.team_admin:
        query = query.filter(or_(Ticket.team_id == user.team_id, Ticket.origin_team_id == user.team_id))
    elif team_id:
        query = query.filter(or_(Ticket.team_id == team_id, Ticket.origin_team_id == team_id))

    tickets = query.all()

    stats: dict[str, dict] = {}
    for t in tickets:
        entry = stats.setdefault(t.closed_by, {"count": 0, "total_hours": 0.0})
        entry["count"] += 1
        if t.closed_at and t.created_at:
            entry["total_hours"] += (t.closed_at - t.created_at).total_seconds() / 3600

    results = []
    for user_id, entry in stats.items():
        closer = db.query(User).filter(User.id == user_id).first()
        if not closer:
            continue
        team = db.query(Team).filter(Team.id == closer.team_id).first() if closer.team_id else None
        results.append(ClosePerformanceEntry(
            user_id=user_id,
            full_name=closer.full_name,
            team_name=team.name if team else None,
            closed_count=entry["count"],
            avg_close_hours=round(entry["total_hours"] / entry["count"], 1) if entry["count"] else None,
        ))

    results.sort(key=lambda r: r.closed_count, reverse=True)
    return results


@router.get("/global")
def global_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    fmt: str = Query("pdf", alias="format"),
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    closed_by_user_id: Optional[str] = None,
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    query = _scoped_query(db, user, "global", team_id, user_id, closed_by_user_id)
    query = _apply_common_filters(query, status_filter, _parse_date(date_from), _parse_date(date_to))
    return _build(query.all(), "Global Ticket Report", fmt, _subtitle(status_filter, date_from, date_to))
