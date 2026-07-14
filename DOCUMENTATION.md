# SME Ticketing System — Documentation

**Version:** 1.0 (Docker Compose deployment)
**Stack:** FastAPI · PostgreSQL · Redis · Celery · React (Vite) · Nginx

---

## 1. Overview

An internal task/process ticketing system for small-to-medium businesses. Employees raise
tickets for their own team or for another team (e.g. IT, Finance, HR), tickets go through
an approval chain before becoming actionable, and every step is tracked in a permanent,
auditable timeline. Includes file attachments, role-scoped reporting (PDF/Excel), a
closer-accountability leaderboard, and in-app notifications.

**Roles:** `normal_user` · `team_admin` · `super_admin` — see [Section 4](#4-roles--permissions).

---

## 2. Architecture

```
                        ┌────────────┐
   Browser  ───────────▶│   nginx    │  reverse proxy (port 8080)
                        └─────┬──────┘
                   ┌──────────┴──────────┐
                   ▼                     ▼
            ┌─────────────┐      ┌──────────────┐
            │  frontend   │      │   backend    │  FastAPI (JWT auth)
            │ React+Vite  │      │              │
            │ served by   │      └──────┬───────┘
            │ its own     │             │
            │ nginx       │      ┌──────┴───────┐
            └─────────────┘      ▼              ▼
                          ┌────────────┐  ┌────────────┐
                          │ PostgreSQL │  │   Redis    │
                          └────────────┘  └──────┬─────┘
                                                   │
                                          ┌────────┴────────┐
                                          ▼                 ▼
                                  ┌──────────────┐  ┌──────────────┐
                                  │celery_worker │  │ celery_beat  │
                                  │ (background  │  │ (scheduled   │
                                  │  jobs)       │  │  SLA checks) │
                                  └──────────────┘  └──────────────┘
```

| Container | Role |
|---|---|
| `nginx` | Single public entry point (port 8080); routes `/` to frontend, `/api` to backend |
| `frontend` | React SPA (Vite build), served by its own lightweight nginx, with SPA fallback routing |
| `backend` | FastAPI app — auth, business logic, all REST endpoints, file uploads, report generation |
| `postgres` | Primary datastore (named volume `postgres_data`) |
| `redis` | Cache + Celery broker/result backend |
| `celery_worker` | Runs background jobs on demand (currently: SLA/overdue checks are triggered by beat) |
| `celery_beat` | Scheduler — runs the SLA/escalation check every 6 hours |

Two additional named volumes: `reports_data` (generated PDF/Excel, currently written
on-the-fly and streamed, not persisted long-term) and `uploads_data` (ticket attachments,
persisted).

**v1 → v2 (Kubernetes) migration path:** each compose service maps 1:1 to a Deployment;
`nginx` becomes an Ingress; `postgres_data`/`uploads_data` become PersistentVolumeClaims
(or move to managed Postgres/S3). Not part of this v1 delivery.

---

## 3. Data Model (core tables)

| Table | Purpose |
|---|---|
| `teams` | `name`, `team_admin_id` (who approves for this team), `is_active` |
| `users` | `email`, `password_hash`, `role`, `team_id`, `is_active` |
| `tickets` | Title/description/priority/status, `created_by`, `assigned_to`, `team_id` (current owner), `origin_team_id` (**permanent**, for audit), `requested_team_id` (target, only set mid-flight), `requested_assigned_to` (hint), `closed_by` (**permanent**, for accountability) |
| `approvals` | One row per approval decision point; `stage` (1 or 2), `approver_id`, `decision` |
| `ticket_status_history` | Every status transition + a human-readable `note` — this is the unified timeline |
| `ticket_comments` | Threaded comments, with author |
| `attachments` | Files attached to a ticket, stored on disk under `uploads_data`, streamed back with a permission check |
| `notifications` | Per-user, linked to a `ticket_id`, drives the notification bell |

**Key design decision — `team_id` vs `origin_team_id`:** `team_id` is *who currently owns*
the ticket (changes as it's redirected or routed cross-team). `origin_team_id` is *who
originally requested it* and never changes. Visibility for team admins is the union of
both, so a team never loses sight of a ticket it raised, even after another team takes
over and closes it.

---

## 4. Roles & Permissions

| Action | normal_user | team_admin | super_admin |
|---|---|---|---|
| Create a ticket (own team) | ✅ | ✅ | ✅ (auto-approved) |
| Create a ticket for another team | ✅ (2-stage approval) | ✅ (2-stage approval) | ✅ (auto-approved) |
| View tickets | own (created or assigned) | own team (current + origin, for audit) | all |
| Approve/reject a ticket | — | tickets routed to them | any pending ticket (override) |
| Start progress (`open`→`in_progress`) | only if assignee | only if their team owns it | always |
| Close a ticket | assignee/owning team | ✅ | ✅ |
| Reopen a closed ticket | ❌ | ✅ | ✅ |
| Redirect a ticket | owner/assignee/owning team admin | ✅ | ✅ |
| Delete a ticket | only own, only while `pending_approval` | ❌ | always |
| Manage teams (create/edit/delete/activate) | ❌ | ❌ | ✅ |
| Manage users (create/edit/delete/activate) | ❌ | ❌ | ✅ |
| Run reports | own tickets only | own team (audit-inclusive) | everything, with filters |
| View closer-performance leaderboard | ❌ | own team | everyone |
| Change own password | ✅ | ✅ | ✅ |

**Approver resolution (the hierarchy):** a `normal_user`'s manager is their team's
`team_admin`. A `team_admin`'s manager is the **super admin** — never themselves, even
though they administer their own team. A `super_admin`'s tickets are always auto-approved.

---

## 5. Ticket Lifecycle

### Statuses
`pending_approval` → `open` → `in_progress` → `closed`, with a `rejected` branch that can
be resubmitted (always restarting approval at stage 1).

### Approval chains

**Same-team ticket** (target team = requester's own team): single-stage approval by the
requester's manager (per the hierarchy above). Approving opens it immediately and lets the
approver assign it to anyone on the team.

**Cross-team ticket** (e.g. HR → IT): two-stage approval —
1. **Stage 1** — the requester's own manager authorizes the request. Ticket stays
   `pending_approval`, ownership (`team_id`) has not moved yet.
2. **Stage 2** — the target team's admin gives final approval. Only now does the ticket
   become `open`, with `team_id` switching to the target team, and the target admin picks
   who it's assigned to (defaulting to the optional "specifically for" hint set at
   creation, or the requester).

Rejection at either stage sends it back to the requester (status `rejected`); resubmission
always restarts at stage 1, regardless of which stage it was rejected at.

### Timeline
Every transition — creation, each approval decision, status change, redirect, SLA
reminder/escalation — is logged to `ticket_status_history` with a plain-English `note`
(e.g. *"Approved by Jane (stage 1) — forwarded to IT for final approval from Sam"*). This
single table is what renders as the ticket's unified timeline in the UI.

---

## 6. Feature Summary

- **File attachments** — images, PDF, Office docs, text/CSV, visible at every stage.
- **Comments** — with author name and timestamp.
- **Audit-safe visibility** — a team keeps seeing tickets it raised even after another
  team takes over and closes them.
- **Closer accountability** — `closed_by` is a permanent record of who actually closed a
  ticket (distinct from current assignee), feeding a rankable performance leaderboard
  (`GET /reports/performance`) for team admins/super admin.
- **SLA monitoring** — Celery beat checks every 6h for tickets stuck in
  `pending_approval` (reminder after 24h, escalation to super admin after another 72h) or
  stale in `open`/`in_progress` (reminder after 72h with no activity). Notifications are
  sent and a note is logged to the timeline.
- **In-app notifications** — bell icon with unread badge, deep-links to the relevant
  ticket, mark-read / mark-all-read.
- **Reporting** — PDF/Excel export scoped to "my tickets" / "my team" (audit-inclusive) /
  "everything" (super admin, with team/user/closer/date-range filters), a live preview of
  what will be exported before downloading, and a two-sheet Excel workbook (Summary +
  Tickets) with color-coded statuses, freeze panes, and autofilter.
- **Sortable/filterable ticket list** — client-side column sort + per-column filters.
- **Team/user lifecycle management** — edit, delete (with dependency guards), and
  activate/deactivate (deactivating a team locks out *all* its members from login).

---

## 7. API Reference (grouped by router)

All endpoints are prefixed and require a Bearer JWT (`Authorization: Bearer <token>`)
except `/auth/login`. Full interactive docs at `/docs` (Swagger UI) when running.

| Router | Key endpoints |
|---|---|
| `auth` | `POST /auth/login`, `POST /auth/refresh` |
| `users` | `GET/POST /users`, `GET/PATCH/DELETE /users/{id}`, `GET /users/team/{team_id}`, `PATCH /users/me/password` |
| `teams` | `GET/POST /teams`, `PATCH/DELETE /teams/{id}` |
| `tickets` | `GET/POST /tickets`, `GET/PATCH/DELETE /tickets/{id}`, `PATCH /tickets/{id}/status`, `POST /tickets/{id}/redirect`, `GET /tickets/{id}/history`, `GET /tickets/{id}/approvals`, `GET/POST /tickets/{id}/comments` |
| `approvals` | `GET /approvals/pending`, `POST /approvals/{id}/decide` |
| `attachments` | `GET/POST /tickets/{id}/attachments`, `GET /attachments/{id}/download`, `DELETE /attachments/{id}` |
| `reports` | `GET /reports/summary`, `GET /reports/me`, `GET /reports/team/{id}`, `GET /reports/global`, `GET /reports/performance` |
| `notifications` | `GET /notifications`, `GET /notifications/unread-count`, `PATCH /notifications/{id}/read`, `POST /notifications/read-all` |

---

## 8. Deployment

```bash
cp .env.example .env      # set JWT_SECRET, POSTGRES_PASSWORD, super admin credentials
docker compose up --build
```
- App: `http://localhost:8080` · API docs: `http://localhost:8080/docs`
- Full reset (schema/data wipe): `docker compose down -v && docker compose up --build`
- Schema is created via SQLAlchemy `create_all()` on startup (see `app/main.py`); Alembic
  is scaffolded under `backend/alembic` for when real migrations are needed.

**Demo organization** (auto-seeded once, on an empty database), all passwords `12345`:

| Team | Team admin | Members |
|---|---|---|
| HR | hr@gmail.com | oelhaj@gmail.com, belhaj@gmail.com |
| Finance | finance@gmail.com | melhaj@gmail.com, telhaj@gmail.com |
| IT | it@gmail.com | aelhaj@gmail.com, felhaj@gmail.com |

The super admin also gets their own "Administration" team, seeded from
`FIRST_SUPER_ADMIN_EMAIL`/`FIRST_SUPER_ADMIN_PASSWORD` in `.env`.

---

## 9. Testing

```bash
cd backend
pip install -r requirements-dev.txt --break-system-packages
pytest -v
```
40 tests against a disposable SQLite database (your real Postgres data is never touched),
covering the full API through FastAPI's TestClient: auth and deactivation gating, the
full ticket lifecycle and every permission boundary, the two-stage cross-team approval
flow (with explicit regression tests for the audit-visibility fix and the team-admin
self-approval bug), attachments, and reporting/notifications. ~13 seconds.

---

## 10. Known Limitations / Recommended Next Steps

Not included in this v1 — flagged here rather than silently, in order of likely impact:

- **No SSO/MFA** — local email+password only. Enterprise deployments typically need
  SAML/OIDC integration and optional MFA.
- **No account lockout / login rate limiting** — unlimited login attempts currently.
- **Email delivery is a stub** (`app/tasks.py:send_notification_email` just logs to
  console) — needs real SMTP/SES/SendGrid wiring.
- **No admin audit log** — role changes, deactivations, deletions aren't logged separately
  from the ticket timeline.
- **No automated backups** — Postgres relies on the named Docker volume; no tested
  backup/restore procedure is included.
- **No CI pipeline** — the pytest suite exists and passes but isn't wired into a
  GitHub Actions / GitLab CI workflow yet.
- **SLA thresholds are hardcoded** (24h/72h) rather than configurable per priority.
- **No bulk actions** (multi-select close/reassign) or CSV user import — fine at current
  scale, would matter for larger rollouts.
