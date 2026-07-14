from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import User, Team, UserRole


def seed_super_admin(db: Session):
    if db.query(User).filter(User.role == UserRole.super_admin).first():
        print("[seed] A super admin already exists — skipping super admin seed. "
              "FIRST_SUPER_ADMIN_EMAIL/PASSWORD in .env will NOT be applied "
              "unless that user is removed or the database is wiped (docker compose down -v).")
        return

    admin = User(
        email=settings.first_super_admin_email,
        password_hash=hash_password(settings.first_super_admin_password),
        full_name="Super Admin",
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    # Super admin gets their own team, with full privileges over it (it's both
    # their team and the one they administer) — keeps them consistent with the
    # team_admin/team_id model instead of being a special-cased null-team user.
    admin_team = Team(name="Administration", team_admin_id=admin.id, is_active=True)
    db.add(admin_team)
    db.flush()
    admin.team_id = admin_team.id

    db.commit()
    print(f"[seed] Created initial super admin: {settings.first_super_admin_email} "
          f"(with their own 'Administration' team)")


# Demo org: 3 teams, each with 1 team admin + 2 normal users. Only runs once —
# if ANY of these emails already exist, the whole demo seed is skipped so it
# never overwrites real data you've since edited.
DEMO_ORG = [
    {
        "team": "HR",
        "admin": {"email": "hr@gmail.com", "full_name": "HR"},
        "members": [
            {"email": "oelhaj@gmail.com", "full_name": "O. Elhaj"},
            {"email": "belhaj@gmail.com", "full_name": "B. Elhaj"},
        ],
    },
    {
        "team": "Finance",
        "admin": {"email": "finance@gmail.com", "full_name": "Finance"},
        "members": [
            {"email": "melhaj@gmail.com", "full_name": "M. Elhaj"},
            {"email": "telhaj@gmail.com", "full_name": "T. Elhaj"},
        ],
    },
    {
        "team": "IT",
        "admin": {"email": "it@gmail.com", "full_name": "IT"},
        "members": [
            {"email": "aelhaj@gmail.com", "full_name": "A. Elhaj"},
            {"email": "felhaj@gmail.com", "full_name": "F. Elhaj"},
        ],
    },
]
DEMO_PASSWORD = "12345"


def seed_demo_data(db: Session):
    all_emails = [DEMO_ORG_ENTRY["admin"]["email"] for DEMO_ORG_ENTRY in DEMO_ORG]
    all_emails += [m["email"] for entry in DEMO_ORG for m in entry["members"]]

    existing = db.query(User).filter(User.email.in_(all_emails)).count()
    if existing > 0:
        print(f"[seed] {existing} demo account(s) already exist — skipping demo data seed.")
        return

    for entry in DEMO_ORG:
        team = db.query(Team).filter(Team.name == entry["team"]).first()
        if not team:
            team = Team(name=entry["team"])
            db.add(team)
            db.flush()

        admin_user = User(
            email=entry["admin"]["email"],
            password_hash=hash_password(DEMO_PASSWORD),
            full_name=entry["admin"]["full_name"],
            role=UserRole.team_admin,
            team_id=team.id,
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

        team.team_admin_id = admin_user.id

        for m in entry["members"]:
            db.add(User(
                email=m["email"],
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=m["full_name"],
                role=UserRole.normal_user,
                team_id=team.id,
                is_active=True,
            ))

    db.commit()
    print(f"[seed] Created demo org: {', '.join(e['team'] for e in DEMO_ORG)} "
          f"(3 teams, {len(DEMO_ORG) * 3} users, password '{DEMO_PASSWORD}' for all).")
