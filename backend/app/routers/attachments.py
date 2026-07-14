import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, Ticket, Attachment
from app.schemas.schemas import AttachmentOut
from app.services import ticket_service

router = APIRouter(tags=["attachments"])

# Kept intentionally conservative for an internal SME tool — images + common
# office/document formats. Extend as needed.
ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
}


def _get_visible_ticket(db: Session, actor: User, ticket_id: str) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if not ticket_service.can_view_ticket(actor, ticket):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this ticket")
    return ticket


def _enrich(db: Session, a: Attachment) -> AttachmentOut:
    out = AttachmentOut.model_validate(a)
    uploader = db.query(User).filter(User.id == a.uploaded_by).first()
    out.uploaded_by_name = uploader.full_name if uploader else None
    return out


@router.get("/tickets/{ticket_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)
    items = db.query(Attachment).filter(Attachment.ticket_id == ticket_id) \
        .order_by(Attachment.created_at.asc()).all()
    return [_enrich(db, a) for a in items]


@router.post("/tickets/{ticket_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(ticket_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    _get_visible_ticket(db, user, ticket_id)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"File type '{file.content_type}' isn't allowed. Use an image, PDF, Office document, or text/CSV file.")

    contents = await file.read()
    if len(contents) > settings.max_attachment_size_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f"File exceeds the {settings.max_attachment_size_bytes // (1024*1024)} MB limit.")

    ticket_dir = os.path.join(settings.upload_root, ticket_id)
    os.makedirs(ticket_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4()}_{os.path.basename(file.filename or 'file')}"
    disk_path = os.path.join(ticket_dir, safe_name)
    with open(disk_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        ticket_id=ticket_id,
        uploaded_by=user.id,
        filename=file.filename or safe_name,
        content_type=file.content_type,
        size_bytes=len(contents),
        storage_path=os.path.join(ticket_id, safe_name),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return _enrich(db, attachment)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")

    ticket = db.query(Ticket).filter(Ticket.id == attachment.ticket_id).first()
    if not ticket or not ticket_service.can_view_ticket(user, ticket):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this attachment")

    disk_path = os.path.join(settings.upload_root, attachment.storage_path)
    if not os.path.isfile(disk_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is missing from storage")

    return FileResponse(disk_path, media_type=attachment.content_type, filename=attachment.filename)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")

    ticket = db.query(Ticket).filter(Ticket.id == attachment.ticket_id).first()
    can_manage = user.role == "super_admin" or attachment.uploaded_by == user.id or (
        ticket and ticket_service.can_touch_ticket(user, ticket)
    )
    if not can_manage:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't remove this attachment")

    disk_path = os.path.join(settings.upload_root, attachment.storage_path)
    if os.path.isfile(disk_path):
        os.remove(disk_path)

    db.delete(attachment)
    db.commit()
