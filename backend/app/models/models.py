import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    normal_user = "normal_user"
    team_admin = "team_admin"
    super_admin = "super_admin"


class TicketStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    open = "open"
    in_progress = "in_progress"
    closed = "closed"
    rejected = "rejected"


class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ApprovalDecision(str, enum.Enum):
    pending = "pending"
    approve = "approve"
    reject = "reject"


class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(120), unique=True, nullable=False)
    team_admin_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", back_populates="team", foreign_keys="User.team_id")
    admin = relationship("User", foreign_keys=[team_admin_id], post_update=True)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.normal_user)
    team_id = Column(UUID(as_uuid=False), ForeignKey("teams.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="members", foreign_keys=[team_id])


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(TicketStatus), nullable=False, default=TicketStatus.pending_approval)
    priority = Column(SAEnum(TicketPriority), nullable=False, default=TicketPriority.medium)

    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=False), ForeignKey("teams.id"), nullable=True)
    # Set once at creation and NEVER changed afterward — the requesting team, kept
    # permanently for audit purposes even after the ticket moves to another team's
    # ownership (team_id changes on cross-team approval / redirect).
    origin_team_id = Column(UUID(as_uuid=False), ForeignKey("teams.id"), nullable=True)
    # Set only while a cross-team request is in flight: the team the ticket is being
    # routed TO. Once stage-2 approval completes, team_id becomes this value and
    # requested_team_id is cleared.
    requested_team_id = Column(UUID(as_uuid=False), ForeignKey("teams.id"), nullable=True)
    # Optional hint set by the requester at creation time: "please give this to
    # this specific person on the target team." The final approver can still
    # override it when they decide.
    requested_assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    # Who actually performed the close action — distinct from assigned_to,
    # since a ticket's current assignee can change (redirect/reopen) but this
    # stays a permanent record of who gets credit for closing it. Used for
    # performance/workload reporting.
    closed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    closer = relationship("User", foreign_keys=[closed_by])
    team = relationship("Team", foreign_keys=[team_id])
    origin_team = relationship("Team", foreign_keys=[origin_team_id])


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    approver_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    # stage 1 = the requester's own team admin (always required).
    # stage 2 = the target team's admin, only created for cross-team requests,
    #           after stage 1 is approved. Same-team tickets never get a stage-2 row.
    stage = Column(Integer, nullable=False, default=1)
    decision = Column(SAEnum(ApprovalDecision), nullable=False, default=ApprovalDecision.pending)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    ticket = relationship("Ticket")
    approver = relationship("User")


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    from_status = Column(SAEnum(TicketStatus), nullable=True)
    to_status = Column(SAEnum(TicketStatus), nullable=False)
    changed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    # Plain-English explanation of what happened at this step, e.g. "Approved by
    # Jane (stage 1) — forwarded to IT for final approval." This is what powers
    # the single combined ticket timeline in the UI.
    note = Column(Text, nullable=True)

    ticket = relationship("Ticket")
    changed_by_user = relationship("User")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    storage_path = Column(String(500), nullable=False)  # path on disk, relative to UPLOAD_ROOT
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket")
    uploader = relationship("User")


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=False)
    author_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket")
    author = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=False), ForeignKey("tickets.id"), nullable=True)
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
