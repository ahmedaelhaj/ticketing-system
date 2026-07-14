from tests.conftest import unique


def _create_ticket(client, headers):
    r = client.post("/tickets", json={"title": unique("attach"), "priority": "low", "target_team_id": None}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def test_upload_list_download_attachment(client, hr_user_headers):
    tid = _create_ticket(client, hr_user_headers)

    files = {"file": ("note.txt", b"hello world", "text/plain")}
    r = client.post(f"/tickets/{tid}/attachments", files=files, headers=hr_user_headers)
    assert r.status_code == 201
    attachment_id = r.json()["id"]
    assert r.json()["size_bytes"] == 11

    r = client.get(f"/tickets/{tid}/attachments", headers=hr_user_headers)
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.get(f"/attachments/{attachment_id}/download", headers=hr_user_headers)
    assert r.status_code == 200
    assert r.content == b"hello world"


def test_disallowed_file_type_rejected(client, hr_user_headers):
    tid = _create_ticket(client, hr_user_headers)
    files = {"file": ("virus.exe", b"MZ...", "application/x-msdownload")}
    r = client.post(f"/tickets/{tid}/attachments", files=files, headers=hr_user_headers)
    assert r.status_code == 400


def test_attachment_access_forbidden_for_unrelated_team(client, hr_user_headers, it_admin_headers):
    tid = _create_ticket(client, hr_user_headers)
    r = client.get(f"/tickets/{tid}/attachments", headers=it_admin_headers)
    assert r.status_code == 403


def test_delete_attachment(client, hr_user_headers):
    tid = _create_ticket(client, hr_user_headers)
    files = {"file": ("temp.txt", b"delete me", "text/plain")}
    r = client.post(f"/tickets/{tid}/attachments", files=files, headers=hr_user_headers)
    attachment_id = r.json()["id"]

    r = client.delete(f"/attachments/{attachment_id}", headers=hr_user_headers)
    assert r.status_code == 204

    r = client.get(f"/tickets/{tid}/attachments", headers=hr_user_headers)
    assert len(r.json()) == 0
