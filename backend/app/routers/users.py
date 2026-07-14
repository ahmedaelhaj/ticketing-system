from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_super_admin, get_current_user
from app.core.security import hash_password, verify_password
from app.models import User, Team
from app.schemas.schemas import UserOut, UserCreate, UserUpdate, ChangePasswordRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def my_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(payload: ChangePasswordRequest, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Any logged-in user can change their own password — no admin needed."""
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if len(payload.new_password) < 5:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be at least 5 characters")

    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.get("/team/{team_id}", response_model=list[UserOut])
def list_team_members(team_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(User).filter(User.team_id == team_id, User.is_active == True).order_by(User.full_name).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A user with this email already exists")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        team_id=payload.team_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db),
                 _: User = Depends(require_super_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    data = payload.model_dump(exclude_unset=True)

    if "email" in data and data["email"] != user.email:
        if db.query(User).filter(User.email == data["email"], User.id != user_id).first():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A user with this email already exists")

    for field, value in data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: Session = Depends(get_db), actor: User = Depends(require_super_admin)):
    if user_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    still_admin_of = db.query(Team).filter(Team.team_admin_id == user_id).first()
    if still_admin_of:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This user is still the team admin for '{still_admin_of.name}'. "
            "Reassign that team's admin first before deleting this user."
        )

    db.delete(user)
    db.commit()
