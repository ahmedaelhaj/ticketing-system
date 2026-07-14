from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_super_admin
from app.models import User, Team
from app.schemas.schemas import TeamOut, TeamCreate, TeamUpdate

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Team).all()


def _sync_admin_team_membership(db: Session, team: Team):
    """Whenever a user is set as a team's admin, they must also belong to that
    team themselves — otherwise the team_admin visibility filter (which is based
    on the admin's own team_id) silently excludes everything."""
    if not team.team_admin_id:
        return
    admin = db.query(User).filter(User.id == team.team_admin_id).first()
    if admin and admin.team_id != team.id:
        admin.team_id = team.id


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    if db.query(Team).filter(Team.name == payload.name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A team with this name already exists")
    team = Team(name=payload.name, team_admin_id=payload.team_admin_id)
    db.add(team)
    db.flush()
    _sync_admin_team_membership(db, team)
    db.commit()
    db.refresh(team)
    return team


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(team_id: str, payload: TeamUpdate, db: Session = Depends(get_db),
                 _: User = Depends(require_super_admin)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)

    _sync_admin_team_membership(db, team)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: str, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    member_count = db.query(User).filter(User.team_id == team_id).count()
    if member_count > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This team still has {member_count} user(s) assigned. "
            "Move or delete them first from the Users page before deleting the team."
        )

    db.delete(team)
    db.commit()
