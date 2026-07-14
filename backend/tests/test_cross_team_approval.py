from tests.conftest import unique


def test_cross_team_two_stage_approval_and_audit_visibility(
    client, hr_user_headers, hr_admin_headers, it_admin_headers, super_admin_headers, team_ids
):
    r = client.post("/tickets", json={
        "title": unique("cross-team"), "priority": "medium", "target_team_id": team_ids["IT"],
    }, headers=hr_user_headers)
    assert r.status_code == 201
    tid = r.json()["id"]

    ticket = client.get(f"/tickets/{tid}", headers=hr_user_headers).json()
    assert ticket["status"] == "pending_approval"
    assert ticket["pending_approval_stage"] == 1
    assert ticket["team_id"] == team_ids["HR"], "stays with origin team during stage 1"

    # IT admin cannot see it yet — still stage 1, not their team's ticket
    r = client.get(f"/tickets/{tid}", headers=it_admin_headers)
    assert r.status_code == 403

    # HR admin approves stage 1 -> forwards to IT, still pending
    r = client.get("/approvals/pending", headers=hr_admin_headers)
    approval1 = next(a for a in r.json() if a["ticket_id"] == tid)
    assert approval1["stage"] == 1
    assert approval1["is_final_stage"] is False
    r = client.post(f"/approvals/{approval1['id']}/decide", json={"decision": "approve"}, headers=hr_admin_headers)
    assert r.status_code == 200

    ticket = client.get(f"/tickets/{tid}", headers=hr_user_headers).json()
    assert ticket["status"] == "pending_approval"
    assert ticket["pending_approval_stage"] == 2
    assert ticket["team_id"] == team_ids["IT"], "ownership moved to target team"

    # Now BOTH HR and IT admins can see it (audit trail)
    assert client.get(f"/tickets/{tid}", headers=hr_admin_headers).status_code == 200
    assert client.get(f"/tickets/{tid}", headers=it_admin_headers).status_code == 200

    # IT admin approves stage 2 (final) -> opens
    r = client.get("/approvals/pending", headers=it_admin_headers)
    approval2 = next(a for a in r.json() if a["ticket_id"] == tid)
    assert approval2["stage"] == 2
    assert approval2["is_final_stage"] is True
    r = client.post(f"/approvals/{approval2['id']}/decide", json={"decision": "approve"}, headers=it_admin_headers)
    assert r.status_code == 200
    assert r.json()["ticket_id"] == tid

    ticket = client.get(f"/tickets/{tid}", headers=hr_user_headers).json()
    assert ticket["status"] == "open"

    # Progress and close it (as IT, who now owns it)
    client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=it_admin_headers)
    r = client.patch(f"/tickets/{tid}/status", json={"status": "closed"}, headers=it_admin_headers)
    assert r.status_code == 200

    # REGRESSION: HR admin (origin team) must still see the closed ticket for audit,
    # even though IT (not HR) now owns and closed it.
    r = client.get(f"/tickets/{tid}", headers=hr_admin_headers)
    assert r.status_code == 200, "origin team lost visibility after close — audit trail bug regressed"

    r = client.get("/tickets", headers=hr_admin_headers)
    assert any(t["id"] == tid for t in r.json()), "closed cross-team ticket missing from origin team's ticket list"


def test_team_admin_ticket_routes_to_super_admin_not_self(
    client, hr_admin_headers, super_admin_headers, team_ids
):
    """Regression test: a team admin's own ticket must never route to themselves
    for approval, even though they administer their own team."""
    r = client.post("/tickets", json={
        "title": unique("admin-same-team"), "priority": "low", "target_team_id": None,
    }, headers=hr_admin_headers)
    tid = r.json()["id"]

    r = client.get(f"/tickets/{tid}/approvals", headers=hr_admin_headers)
    pending = next(a for a in r.json() if a["decision"] == "pending")

    r = client.get("/users/me", headers=super_admin_headers)
    sa_id = r.json()["id"]
    assert pending["approver_id"] == sa_id

    r = client.get("/users/me", headers=hr_admin_headers)
    hr_admin_id = r.json()["id"]
    assert pending["approver_id"] != hr_admin_id


def test_team_admin_cross_team_ticket_also_routes_to_super_admin(
    client, hr_admin_headers, super_admin_headers, team_ids
):
    r = client.post("/tickets", json={
        "title": unique("admin-cross-team"), "priority": "medium", "target_team_id": team_ids["IT"],
    }, headers=hr_admin_headers)
    tid = r.json()["id"]

    r = client.get(f"/tickets/{tid}/approvals", headers=hr_admin_headers)
    pending = next(a for a in r.json() if a["decision"] == "pending")

    r = client.get("/users/me", headers=super_admin_headers)
    sa_id = r.json()["id"]
    assert pending["approver_id"] == sa_id
    assert pending["stage"] == 1


def test_team_admin_can_see_all_teams(client, hr_admin_headers, team_ids):
    """Regression test: a team admin must see every team (needed to create
    cross-team tickets), not just their own."""
    r = client.get("/teams", headers=hr_admin_headers)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert {"HR", "Finance", "IT"}.issubset(names)


def test_super_admin_can_override_approve_any_pending_ticket(
    client, hr_user_headers, hr_admin_headers, super_admin_headers
):
    r = client.post("/tickets", json={
        "title": unique("override"), "priority": "low", "target_team_id": None,
    }, headers=hr_user_headers)
    tid = r.json()["id"]

    r = client.get("/approvals/pending", headers=super_admin_headers)
    approval = next(a for a in r.json() if a["ticket_id"] == tid)

    r = client.post(f"/approvals/{approval['id']}/decide", json={"decision": "approve"}, headers=super_admin_headers)
    assert r.status_code == 200, "super admin should be able to override any pending approval"


def test_rejection_and_resubmission_restarts_at_stage_1(
    client, hr_user_headers, hr_admin_headers, it_admin_headers, team_ids
):
    r = client.post("/tickets", json={
        "title": unique("reject-resubmit"), "priority": "low", "target_team_id": team_ids["IT"],
    }, headers=hr_user_headers)
    tid = r.json()["id"]

    r = client.get("/approvals/pending", headers=hr_admin_headers)
    approval = next(a for a in r.json() if a["ticket_id"] == tid)
    client.post(f"/approvals/{approval['id']}/decide", json={"decision": "reject", "comment": "not now"}, headers=hr_admin_headers)

    ticket = client.get(f"/tickets/{tid}", headers=hr_user_headers).json()
    assert ticket["status"] == "rejected"

    r = client.patch(f"/tickets/{tid}/status", json={"status": "pending_approval"}, headers=hr_user_headers)
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["status"] == "pending_approval"
    assert ticket["pending_approval_stage"] == 1
