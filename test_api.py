import threading

import pytest

import api


@pytest.fixture
def client(tmp_path):
    app = api.create_app(tmp_path / "test.db")
    return app.test_client()


def test_add_user_returns_201_with_id_and_location(client):
    r = client.post("/adduser", json={"name": "alice"})
    assert r.status_code == 201
    assert r.get_json() == {"id": 1, "name": "alice"}
    assert r.headers["Location"] == "/user/1"


def test_get_user_returns_200(client):
    client.post("/adduser", json={"name": "alice"})
    r = client.get("/user/1")
    assert r.status_code == 200
    assert r.get_json() == {"id": 1, "name": "alice"}


def test_get_missing_user_returns_404(client):
    r = client.get("/user/999")
    assert r.status_code == 404
    assert r.get_json() == {"error": "user not found"}


@pytest.mark.parametrize("path", ["/user/abc", "/user/0%20OR%201=1", "/user/0%20UNION%20SELECT%201,2"])
def test_get_user_rejects_non_integer_id(client, path):
    client.post("/adduser", json={"name": "alice"})
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "name=bob"},
        {"json": None},
        {"json": ["bob"]},
        {"json": {}},
        {"json": {"name": ""}},
        {"json": {"name": "   "}},
        {"json": {"name": 42}},
    ],
)
def test_add_user_rejects_bad_payload(client, kwargs):
    r = client.post("/adduser", **kwargs)
    assert r.status_code == 400
    assert "error" in r.get_json()


@pytest.mark.parametrize("name", ["O'Brien", "x'),('pwned", "'; DROP TABLE users; --"])
def test_names_with_quotes_are_stored_verbatim(client, name):
    r = client.post("/adduser", json={"name": name})
    assert r.status_code == 201
    assert client.get(f"/user/{r.get_json()['id']}").get_json()["name"] == name
    # инъекция не создала лишних строк
    assert client.get("/user/2").status_code == 404


def test_add_user_only_accepts_post(client):
    assert client.get("/adduser").status_code == 405


def test_concurrent_requests(client):
    ids, errors = [], []
    lock = threading.Lock()

    def worker(n):
        for i in range(10):
            r = client.post("/adduser", json={"name": f"u{n}-{i}"})
            with lock:
                (ids if r.status_code == 201 else errors).append(r.get_json())

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sorted(r["id"] for r in ids) == list(range(1, 201))
