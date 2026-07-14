def test_login_success(client):
    r = client.post("/auth/login", json={"email": "admin@company.com", "password": "ChangeMe123!"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"email": "admin@company.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/auth/login", json={"email": "nobody@nowhere.com", "password": "x"})
    assert r.status_code == 401


def test_deactivated_user_blocked_from_login(client, super_admin_headers):
    r = client.post("/users", json={
        "email": "deactivate-me@test.com", "password": "12345",
        "full_name": "Temp User", "role": "normal_user",
    }, headers=super_admin_headers)
    assert r.status_code == 201
    user_id = r.json()["id"]

    r = client.patch(f"/users/{user_id}", json={"is_active": False}, headers=super_admin_headers)
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.post("/auth/login", json={"email": "deactivate-me@test.com", "password": "12345"})
    assert r.status_code == 403
    assert "deactivated" in r.json()["detail"].lower()

    # reactivate, should work again
    client.patch(f"/users/{user_id}", json={"is_active": True}, headers=super_admin_headers)
    r = client.post("/auth/login", json={"email": "deactivate-me@test.com", "password": "12345"})
    assert r.status_code == 200


def test_deactivated_team_blocks_all_members(client, super_admin_headers, team_ids):
    hr_id = team_ids["HR"]

    r = client.patch(f"/teams/{hr_id}", json={"is_active": False}, headers=super_admin_headers)
    assert r.status_code == 200

    for email in ["hr@gmail.com", "oelhaj@gmail.com", "belhaj@gmail.com"]:
        r = client.post("/auth/login", json={"email": email, "password": "12345"})
        assert r.status_code == 403, f"{email} should be blocked while team is inactive"
        assert "deactivated" in r.json()["detail"].lower()

    # An unrelated team is unaffected
    r = client.post("/auth/login", json={"email": "finance@gmail.com", "password": "12345"})
    assert r.status_code == 200

    # Reactivate so later tests aren't affected
    r = client.patch(f"/teams/{hr_id}", json={"is_active": True}, headers=super_admin_headers)
    assert r.status_code == 200
    r = client.post("/auth/login", json={"email": "hr@gmail.com", "password": "12345"})
    assert r.status_code == 200


def test_refresh_token_flow(client):
    r = client.post("/auth/login", json={"email": "admin@company.com", "password": "ChangeMe123!"})
    refresh_token = r.json()["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_self_service_password_change(client, login):
    headers = login("oelhaj@gmail.com")
    r = client.patch("/users/me/password", json={"current_password": "12345", "new_password": "newpass1"}, headers=headers)
    assert r.status_code == 204

    r = client.post("/auth/login", json={"email": "oelhaj@gmail.com", "password": "newpass1"})
    assert r.status_code == 200
    r = client.post("/auth/login", json={"email": "oelhaj@gmail.com", "password": "12345"})
    assert r.status_code == 401

    # wrong current password rejected
    headers2 = login("oelhaj@gmail.com", "newpass1")
    r = client.patch("/users/me/password", json={"current_password": "wrong", "new_password": "whatever1"}, headers=headers2)
    assert r.status_code == 400

    # revert so other tests relying on the original password still work
    client.patch("/users/me/password", json={"current_password": "newpass1", "new_password": "12345"}, headers=headers2)
