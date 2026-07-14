from tests.conftest import unique


def test_create_team_with_admin_syncs_team_id(client, super_admin_headers):
    admin_email = unique("newadmin") + "@test.com"
    r = client.post("/users", json={
        "email": admin_email, "password": "12345", "full_name": "New Admin", "role": "team_admin",
    }, headers=super_admin_headers)
    assert r.status_code == 201
    admin_id = r.json()["id"]

    team_name = unique("Team")
    r = client.post("/teams", json={"name": team_name, "team_admin_id": admin_id}, headers=super_admin_headers)
    assert r.status_code == 201
    team_id = r.json()["id"]

    # REGRESSION: creating a team with an admin must sync the admin's own team_id
    r = client.get(f"/users/{admin_id}", headers=super_admin_headers)
    assert r.json()["team_id"] == team_id


def test_reassigning_team_admin_syncs_new_admins_team_id(client, super_admin_headers):
    team_name = unique("Team")
    r = client.post("/teams", json={"name": team_name}, headers=super_admin_headers)
    team_id = r.json()["id"]

    admin_email = unique("admin2") + "@test.com"
    r = client.post("/users", json={
        "email": admin_email, "password": "12345", "full_name": "Second Admin", "role": "team_admin",
    }, headers=super_admin_headers)
    admin_id = r.json()["id"]

    r = client.patch(f"/teams/{team_id}", json={"team_admin_id": admin_id}, headers=super_admin_headers)
    assert r.status_code == 200

    r = client.get(f"/users/{admin_id}", headers=super_admin_headers)
    assert r.json()["team_id"] == team_id


def test_delete_team_blocked_while_it_has_members(client, super_admin_headers, team_ids):
    r = client.delete(f"/teams/{team_ids['HR']}", headers=super_admin_headers)
    assert r.status_code == 409


def test_delete_team_succeeds_once_empty(client, super_admin_headers):
    team_name = unique("EmptyTeam")
    r = client.post("/teams", json={"name": team_name}, headers=super_admin_headers)
    team_id = r.json()["id"]

    r = client.delete(f"/teams/{team_id}", headers=super_admin_headers)
    assert r.status_code == 204


def test_duplicate_email_rejected_on_user_edit(client, super_admin_headers):
    email_a = unique("usera") + "@test.com"
    email_b = unique("userb") + "@test.com"
    r = client.post("/users", json={"email": email_a, "password": "12345", "full_name": "A", "role": "normal_user"}, headers=super_admin_headers)
    r2 = client.post("/users", json={"email": email_b, "password": "12345", "full_name": "B", "role": "normal_user"}, headers=super_admin_headers)
    user_b_id = r2.json()["id"]

    r = client.patch(f"/users/{user_b_id}", json={"email": email_a}, headers=super_admin_headers)
    assert r.status_code == 400


def test_cannot_delete_user_who_is_still_team_admin(client, super_admin_headers, team_ids):
    r = client.get("/users", headers=super_admin_headers)
    hr_admin = next(u for u in r.json() if u["email"] == "hr@gmail.com")

    r = client.delete(f"/users/{hr_admin['id']}", headers=super_admin_headers)
    assert r.status_code == 409


def test_normal_user_cannot_access_admin_endpoints(client, hr_user_headers):
    assert client.get("/users", headers=hr_user_headers).status_code == 403
    assert client.post("/teams", json={"name": "x"}, headers=hr_user_headers).status_code == 403
