from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models import UserRole, TicketStatus, TicketPriority, ApprovalDecision


# ---------- Auth ----------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- User ----------

class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    team_id: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.normal_user
    team_id: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    team_id: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------- Team ----------

class TeamOut(BaseModel):
    id: str
    name: str
    team_admin_id: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class TeamCreate(BaseModel):
    name: str
    team_admin_id: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    team_admin_id: Optional[str] = None
    is_active: Optional[bool] = None


# ---------- Ticket ----------

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TicketPriority = TicketPriority.medium
    assigned_to: Optional[str] = None       # super admin only: assign directly on creation
    target_team_id: Optional[str] = None    # only meaningful when different from the creator's own team
    requested_assigned_to: Optional[str] = None  # optional hint: "please give this to this specific person"


class TicketUpdateStatus(BaseModel):
    status: TicketStatus


class TicketRedirect(BaseModel):
    assigned_to: str
    team_id: Optional[str] = None


class TicketOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: TicketStatus
    priority: TicketPriority

    created_by: str
    created_by_name: Optional[str] = None

    assigned_to: Optional[str]
    assigned_to_name: Optional[str] = None

    requested_assigned_to: Optional[str] = None
    requested_assigned_to_name: Optional[str] = None

    team_id: Optional[str]
    team_name: Optional[str] = None
    team_admin_name: Optional[str] = None

    origin_team_id: Optional[str] = None
    origin_team_name: Optional[str] = None

    requested_team_id: Optional[str]
    requested_team_name: Optional[str] = None

    # If status is pending_approval, which stage it's currently sitting at (1 or 2). Null otherwise.
    pending_approval_stage: Optional[int] = None

    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    closed_by: Optional[str] = None
    closed_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    body: str


class CommentOut(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    author_name: Optional[str] = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Attachments ----------

class AttachmentOut(BaseModel):
    id: str
    ticket_id: str
    uploaded_by: str
    uploaded_by_name: Optional[str] = None
    filename: str
    content_type: Optional[str]
    size_bytes: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Approval ----------

class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    comment: Optional[str] = None
    assigned_to: Optional[str] = None  # who to assign the ticket to on final approval


class ApprovalOut(BaseModel):
    id: str
    ticket_id: str
    approver_id: str
    approver_name: Optional[str] = None
    stage: int
    decision: ApprovalDecision
    comment: Optional[str]
    created_at: datetime
    decided_at: Optional[datetime]

    # ticket context, denormalized here so the approvals queue needs one request
    ticket_title: Optional[str] = None
    ticket_priority: Optional[str] = None
    requester_name: Optional[str] = None
    team_name: Optional[str] = None
    requested_team_name: Optional[str] = None
    is_final_stage: Optional[bool] = None
    current_team_id: Optional[str] = None  # team whose members can be picked as assignee, on final stage

    class Config:
        from_attributes = True


# ---------- Ticket status history (the unified timeline) ----------

class TicketStatusHistoryOut(BaseModel):
    id: str
    from_status: Optional[TicketStatus]
    to_status: TicketStatus
    changed_by: str
    changed_by_name: Optional[str] = None
    changed_at: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Performance / accountability ----------

class ClosePerformanceEntry(BaseModel):
    user_id: str
    full_name: str
    team_name: Optional[str] = None
    closed_count: int
    avg_close_hours: Optional[float] = None


class ReportSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]


# ---------- Notifications ----------

class NotificationOut(BaseModel):
    id: str
    ticket_id: Optional[str] = None
    ticket_title: Optional[str] = None
    type: str
    message: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True
