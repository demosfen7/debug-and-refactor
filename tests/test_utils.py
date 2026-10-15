import threading

import pytest

from app.utils import active_users
from app.utils.active_users import ActiveUsers
from app.utils.passwords import check_password, hash_password
from app.utils.validation import is_valid_name, name_from_payload


# --- passwords ---------------------------------------------------------------

def test_password_hash_roundtrip():
    stored = hash_password("s3cret")
    assert check_password("s3cret", stored)
    assert not check_password("wrong", stored)


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_password_hash_format():
    algo, n, r, p, salt, digest = hash_password("pw").split("$")
    assert (algo, n, r, p) == ("scrypt", str(2**14), "8", "1")
    assert len(bytes.fromhex(salt)) == 16
    assert len(bytes.fromhex(digest)) == 64


# --- validation --------------------------------------------------------------

@pytest.mark.parametrize("value", ["alice", " a ", "O'Brien"])
def test_valid_names(value):
    assert is_valid_name(value)


@pytest.mark.parametrize("value", ["", "   ", "\t\n", None, 42, ["alice"]])
def test_invalid_names(value):
    assert not is_valid_name(value)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"name": "alice"}, "alice"),
        ({"name": ""}, None),
        ({"name": 42}, None),
        ({}, None),
        (["alice"], None),
        (None, None),
        ("alice", None),
    ],
)
def test_name_from_payload(payload, expected):
    assert name_from_payload(payload) == expected


# --- active users ------------------------------------------------------------

def test_active_users_keeps_last_unique():
    tracker = ActiveUsers(limit=5)
    for uid in [1, 2, 3, 2, 4, 5, 6, 7]:
        tracker.mark(uid)
    # повторная активация двигает 2 в конец, самые давние (1, 3) вытесняются
    assert tracker.snapshot() == [2, 4, 5, 6, 7]


def test_active_users_is_thread_safe():
    tracker = ActiveUsers(limit=5)
    barrier = threading.Barrier(50)

    def worker(uid):
        barrier.wait()
        for _ in range(200):
            tracker.mark(uid)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snapshot = tracker.snapshot()
    assert len(snapshot) == 5
    assert len(set(snapshot)) == 5


def test_module_level_active_users():
    active_users._default.clear()
    try:
        active_users.set_active(1)
        active_users.set_active(2)
        assert active_users.get_active_users() == [1, 2]
    finally:
        active_users._default.clear()
