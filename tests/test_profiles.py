import sqlite3
from contextlib import closing

import pytest

from app.repositories import profiles


@pytest.fixture
def db(tmp_path):
    return tmp_path / "users.db"


def test_add_user_creates_table_and_returns_int_id(db):
    assert profiles.add_user("alice", db_path=db) == 1
    assert profiles.add_user("bob", db_path=db) == 2


def test_add_user_does_not_mutate_caller_tags(db):
    tags = ["admin"]
    profiles.add_user("alice", tags, db_path=db)
    assert tags == ["admin"]


def test_add_user_default_tags_do_not_accumulate(db):
    profiles.add_user("alice", db_path=db)
    profiles.add_user("bob", db_path=db)
    assert profiles.get_user_by_name("bob", db_path=db)["tags"] == ["new"]


def test_add_user_does_not_duplicate_new_tag(db):
    profiles.add_user("alice", ["new", "admin"], db_path=db)
    assert profiles.get_user_by_name("alice", db_path=db)["tags"] == ["new", "admin"]


@pytest.mark.parametrize("bad_name", ["", "   ", None, 42])
def test_add_user_rejects_bad_name(db, bad_name):
    with pytest.raises(ValueError):
        profiles.add_user(bad_name, db_path=db)


@pytest.mark.parametrize("name", ["O'Brien", "x'); DROP TABLE users; --", 'quote"s'])
def test_names_with_quotes_are_stored_verbatim(db, name):
    uid = profiles.add_user(name, db_path=db)
    assert profiles.get_user_by_name(name, db_path=db) == {
        "id": uid, "name": name, "tags": ["new"],
    }


def test_get_user_by_name_is_not_injectable(db):
    profiles.add_user("alice", db_path=db)
    assert profiles.get_user_by_name("nobody' OR '1'='1", db_path=db) is None


def test_get_user_by_name_missing_returns_none(db):
    assert profiles.get_user_by_name("ghost", db_path=db) is None


def test_get_user_by_name_decodes_tags(db):
    profiles.add_user("alice", ["admin"], db_path=db)
    assert profiles.get_user_by_name("alice", db_path=db)["tags"] == ["admin", "new"]


def test_password_roundtrip(db):
    uid = profiles.add_user("alice", db_path=db)
    profiles.store_password(uid, "s3cret", db_path=db)
    assert profiles.verify_password(uid, "s3cret", db_path=db)
    assert not profiles.verify_password(uid, "wrong", db_path=db)


def test_password_is_not_stored_in_plaintext(db):
    uid = profiles.add_user("alice", db_path=db)
    profiles.store_password(uid, "same", db_path=db)
    with closing(sqlite3.connect(db)) as conn:
        (stored,) = conn.execute("SELECT password_hash FROM users").fetchone()
    assert "same" not in stored and "emas" not in stored


def test_store_password_unknown_user(db):
    with pytest.raises(LookupError):
        profiles.store_password(999, "pw", db_path=db)


def test_store_password_rejects_empty(db):
    uid = profiles.add_user("alice", db_path=db)
    with pytest.raises(ValueError):
        profiles.store_password(uid, "", db_path=db)


def test_verify_password_without_password_or_user(db):
    uid = profiles.add_user("alice", db_path=db)
    assert not profiles.verify_password(uid, "x", db_path=db)
    assert not profiles.verify_password(999, "x", db_path=db)
