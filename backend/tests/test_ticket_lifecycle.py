from tests.conftest import unique


def _create_same_team_ticket(client, headers, title=None):
    r = client.post("/tickets", json={
        "title": title or unique("ticket"), "priority": "low", "target_team_id": None,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _approve(client, ticket_id, approver_headers):
    r = client.get("/approvals/pending", headers=approver_headers)
    approval = next(a for a in r.json() if a["ticket_id"] == ticket_id)
    r = client.post(f"/approvals/{approval['id']}/decide", json={"decision": "approve"}, headers=approver_headers)
    assert r.status_code == 200, r.text
    return approval


def test_same_team_ticket_full_lifecycle(client, hr_user_headers, hr_admin_headers):
    tid = _create_same_team_ticket(client, hr_user_headers)

    r = client.get(f"/tickets/{tid}", headers=hr_user_headers)
    assert r.json()["status"] == "pending_approval"

    _approve(client, tid, hr_admin_headers)
    r = client.get(f"/tickets/{tid}", headers=hr_user_headers)
    ticket = r.json()
    assert ticket["status"] == "open"
    assignee_id = ticket["assigned_to"]

    r = client.get("/users/me", headers=hr_user_headers)
    requester_id = r.json()["id"]
    assert assignee_id == requester_id, "defaults to requester when no assignee specified"

    r = client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=hr_user_headers)
    assert r.status_code == 200
    r = client.patch(f"/tickets/{tid}/status", json={"status": "closed"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert r.json()["closed_by_name"] is not None


def test_start_progress_restricted_to_assignee_team_admin_super_admin(
    client, hr_user_headers, hr_user2_headers, hr_admin_headers, super_admin_headers
):
    tid = _create_same_team_ticket(client, hr_user_headers)
    approval = _approve(client, tid, hr_admin_headers)

    r = client.get(f"/tickets/{tid}", headers=hr_user_headers)
    assignee_id = r.json()["assigned_to"]
    r = client.get("/users/me", headers=hr_user2_headers)
    other_user_id = r.json()["id"]

    if assignee_id == other_user_id:
        # assignee happened to be hr_user2 by default; swap the test roles
        actor_headers, blocked_headers = hr_user2_headers, hr_user_headers
    else:
        actor_headers, blocked_headers = hr_user_headers, hr_user2_headers

    # A random other normal user (not assignee, not team admin) is blocked
    r = client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=blocked_headers)
    assert r.status_code == 403

    # The actual assignee succeeds
    r = client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=actor_headers)
    assert r.status_code == 200


def test_reopen_restricted_to_team_admin_and_super_admin(client, hr_user_headers, hr_admin_headers):
    tid = _create_same_team_ticket(client, hr_user_headers)
    _approve(client, tid, hr_admin_headers)
    client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=hr_user_headers)
    client.patch(f"/tickets/{tid}/status", json={"status": "closed"}, headers=hr_user_headers)

    # normal user (even if they're the assignee) cannot reopen
    r = client.patch(f"/tickets/{tid}/status", json={"status": "open"}, headers=hr_user_headers)
    assert r.status_code == 403

    # team admin can
    r = client.patch(f"/tickets/{tid}/status", json={"status": "open"}, headers=hr_admin_headers)
    assert r.status_code == 200
    assert r.json()["closed_by_name"] is None, "closed_by should clear on reopen"


def test_delete_only_allowed_for_requester_while_pending_approval(
    client, hr_user_headers, hr_user2_headers, hr_admin_headers, super_admin_headers
):
    # Requester can delete while pending
    tid = _create_same_team_ticket(client, hr_user_headers)
    r = client.delete(f"/tickets/{tid}", headers=hr_user_headers)
    assert r.status_code == 204

    # A different user cannot delete someone else's pending ticket
    tid2 = _create_same_team_ticket(client, hr_user_headers)
    r = client.delete(f"/tickets/{tid2}", headers=hr_user2_headers)
    assert r.status_code == 403

    # Once rejected, requester can no longer delete it (narrowed rule)
    tid3 = _create_same_team_ticket(client, hr_user_headers)
    r = client.get("/approvals/pending", headers=hr_admin_headers)
    approval = next(a for a in r.json() if a["ticket_id"] == tid3)
    client.post(f"/approvals/{approval['id']}/decide", json={"decision": "reject", "comment": "no"}, headers=hr_admin_headers)
    r = client.delete(f"/tickets/{tid3}", headers=hr_user_headers)
    assert r.status_code == 403

    # Super admin can always delete regardless of status
    r = client.delete(f"/tickets/{tid3}", headers=super_admin_headers)
    assert r.status_code == 204
