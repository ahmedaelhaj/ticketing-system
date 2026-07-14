# SME Ticketing System — v1

Internal task/process ticketing system with role-based approval workflow.

## Stack
FastAPI · PostgreSQL · Redis · Celery (worker + beat) · React (Vite) · Nginx · Docker Compose

## Quick start
```bash
cp .env.example .env        # edit values, especially JWT_SECRET and passwords
docker compose up --build
```
App available at http://localhost:8080
API docs at http://localhost:8080/docs

A super admin account is auto-created on first boot from FIRST_SUPER_ADMIN_EMAIL /
FIRST_SUPER_ADMIN_PASSWORD in .env — log in with that, then create teams and users.

## Demo organization (auto-seeded on first boot)
Three teams, each with a team admin + 2 normal users, all password `12345`:

| Team | Team admin | Members |
|---|---|---|
| HR | hr@gmail.com | oelhaj@gmail.com, belhaj@gmail.com |
| Finance | finance@gmail.com | melhaj@gmail.com, telhaj@gmail.com |
| IT | it@gmail.com | aelhaj@gmail.com, felhaj@gmail.com |

Like the super admin seed, this only runs once against an empty database — if you've
already got data, wipe it first (`docker compose down -v`) to get this demo org.

## Features
- Full role-based ticketing (normal user / team admin / super admin) with a
  two-stage cross-team approval chain (origin team admin authorizes, target team
  admin gives final approval) and single-stage same-team approval.
- File attachments (images, PDF, Office docs, text/CSV) on any ticket, visible
  at every stage of its lifecycle.
- Full audit trail: a team keeps visibility into tickets it originally requested
  even after ownership moves to another team and the ticket is closed.
- Unified ticket timeline combining status changes and approval decisions into
  one clear, chronological view.
- PDF/Excel reporting scoped to "my tickets" (any role), "my team" (team admin,
  audit-inclusive), or global with filters (super admin), plus a "who's closing
  tickets" performance leaderboard (team admin / super admin).
- In-app notifications (bell icon, unread badge, mark read/read-all) for approval
  requests, redirects, decisions, and SLA reminders — deep-links to the ticket.

## Running the test suite
```bash
cd backend
pip install -r requirements-dev.txt --break-system-packages   # adds pytest + httpx on top of requirements.txt
pytest -v
```
Or inside the running container:
```bash
docker compose exec backend sh -c "pip install -r requirements-dev.txt && pytest -v"
```
Tests run against a throwaway SQLite file (created fresh per run, not your real
Postgres data) and exercise the full API through FastAPI's TestClient — including
regression tests for the cross-team audit-visibility fix, the team-admin
self-approval bug fix, and every permission boundary (start-progress, delete,
reopen, team/user deactivation). 37 tests, ~15s.

## v1 notes
- Schema is created via SQLAlchemy `create_all()` on backend startup (see app/main.py).
  Alembic is fully scaffolded (backend/alembic) for when you want real migrations —
  once you do, remove the create_all() call and run:
  `docker compose exec backend alembic revision --autogenerate -m "init"`
  `docker compose exec backend alembic upgrade head`
- Reports (PDF/Excel) are generated in app/services/report_service.py and written to
  the `reports_data` volume, shared between backend and celery_worker.
- Celery beat replaces the need for a cron container — see celery_app.py's beat_schedule.

## Roles
normal_user · team_admin · super_admin — see approval chain and status transitions
discussed in project design (Pending approval → Open → In progress → Closed, with
Rejected and reopen paths). Full rules enforced in app/services/ticket_service.py.

## Next step: Kubernetes (v2)
Each compose service maps 1:1 to a Deployment; nginx becomes an Ingress;
postgres_data/reports_data become PersistentVolumeClaims (or move to managed
Postgres/S3). Not part of this v1 delivery.
