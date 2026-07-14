from tests.conftest import unique


def test_my_report_downloads(client, hr_user_headers):
    r = client.get("/reports/me", params={"format": "pdf"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_my_report_excel_format(client, hr_user_headers):
    r = client.get("/reports/me", params={"format": "xlsx"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


def test_team_report_forbidden_for_normal_user(client, hr_user_headers, team_ids):
    r = client.get(f"/reports/team/{team_ids['HR']}", headers=hr_user_headers)
    assert r.status_code == 403


def test_team_report_forbidden_for_other_teams_admin(client, hr_admin_headers, team_ids):
    r = client.get(f"/reports/team/{team_ids['IT']}", headers=hr_admin_headers)
    assert r.status_code == 403


def test_global_report_super_admin_only(client, hr_admin_headers, super_admin_headers):
    r = client.get("/reports/global", headers=hr_admin_headers)
    assert r.status_code == 403

    r = client.get("/reports/global", headers=super_admin_headers)
    assert r.status_code == 200


def test_performance_leaderboard_ranks_by_closed_count(
    client, it_admin_headers, it_user_headers, login, team_ids
):
    # Close 2 tickets as it_user, approved by it_admin
    for _ in range(2):
        r = client.post("/tickets", json={"title": unique("perf"), "priority": "low", "target_team_id": None}, headers=it_user_headers)
        tid = r.json()["id"]
        r = client.get("/approvals/pending", headers=it_admin_headers)
        approval = next(a for a in r.json() if a["ticket_id"] == tid)
        client.post(f"/approvals/{approval['id']}/decide", json={"decision": "approve"}, headers=it_admin_headers)
        client.patch(f"/tickets/{tid}/status", json={"status": "in_progress"}, headers=it_user_headers)
        client.patch(f"/tickets/{tid}/status", json={"status": "closed"}, headers=it_user_headers)

    r = client.get("/reports/performance", headers=it_admin_headers)
    assert r.status_code == 200
    entry = next((e for e in r.json() if e["full_name"] == "A. Elhaj"), None)
    assert entry is not None
    assert entry["closed_count"] >= 2


def test_performance_leaderboard_forbidden_for_normal_user(client, hr_user_headers):
    r = client.get("/reports/performance", headers=hr_user_headers)
    assert r.status_code == 403


def test_notification_created_on_ticket_submission_and_marked_read(
    client, hr_user_headers, hr_admin_headers
):
    r = client.get("/notifications/unread-count", headers=hr_admin_headers)
    baseline = r.json()["count"]

    r = client.post("/tickets", json={"title": unique("notif"), "priority": "low", "target_team_id": None}, headers=hr_user_headers)
    tid = r.json()["id"]

    r = client.get("/notifications/unread-count", headers=hr_admin_headers)
    assert r.json()["count"] == baseline + 1

    r = client.get("/notifications", headers=hr_admin_headers)
    notif = next(n for n in r.json() if n["ticket_id"] == tid)
    assert notif["read"] is False
    assert notif["ticket_title"] is not None

    r = client.patch(f"/notifications/{notif['id']}/read", headers=hr_admin_headers)
    assert r.status_code == 200 and r.json()["read"] is True

    r = client.get("/notifications/unread-count", headers=hr_admin_headers)
    assert r.json()["count"] == baseline


def test_mark_all_read(client, hr_user_headers, hr_admin_headers):
    client.post("/tickets", json={"title": unique("bulk1"), "priority": "low", "target_team_id": None}, headers=hr_user_headers)
    client.post("/tickets", json={"title": unique("bulk2"), "priority": "low", "target_team_id": None}, headers=hr_user_headers)

    r = client.post("/notifications/read-all", headers=hr_admin_headers)
    assert r.status_code == 204

    r = client.get("/notifications/unread-count", headers=hr_admin_headers)
    assert r.json()["count"] == 0


def test_report_summary_preview(client, hr_user_headers):
    r = client.get("/reports/summary", params={"scope": "mine"}, headers=hr_user_headers)
    assert r.status_code == 200
    data = r.json()
    assert "total" in data and "by_status" in data and "by_priority" in data


def test_report_date_range_filtering(client, hr_user_headers):
    r = client.post("/tickets", json={"title": unique("daterange"), "priority": "low", "target_team_id": None}, headers=hr_user_headers)
    assert r.status_code == 201

    r = client.get("/reports/summary", params={
        "scope": "mine", "date_from": "2020-01-01", "date_to": "2020-01-02",
    }, headers=hr_user_headers)
    assert r.json()["total"] == 0

    r = client.get("/reports/summary", params={"scope": "mine", "date_from": "2020-01-01"}, headers=hr_user_headers)
    assert r.json()["total"] >= 1


def test_report_pdf_and_excel_handle_special_characters_and_empty_results(client, hr_user_headers, hr_admin_headers):
    r = client.post("/tickets", json={
        "title": 'Fix <critical> bug & "urgent" issue', "priority": "high", "target_team_id": None,
    }, headers=hr_user_headers)
    tid = r.json()["id"]
    r = client.get("/approvals/pending", headers=hr_admin_headers)
    approval = next(a for a in r.json() if a["ticket_id"] == tid)
    client.post(f"/approvals/{approval['id']}/decide", json={"decision": "approve"}, headers=hr_admin_headers)

    r = client.get("/reports/me", params={"format": "pdf"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    r = client.get("/reports/me", params={"format": "xlsx"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert len(r.content) > 1000

    r = client.get("/reports/me", params={"format": "pdf", "status": "rejected"}, headers=hr_user_headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
