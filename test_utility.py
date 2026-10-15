import threading

import pytest

import utility


@pytest.fixture
def db(tmp_path):
    return tmp_path / "users.db"


@pytest.fixture(autouse=True)
def reset_active_users():
    utility._active_users.clear()
    yield
    utility._active_users.clear()


def test_add_user_creates_table_and_returns_int_id(db):
    assert utility.add_user("alice", db_path=db) == 1
    assert utility.add_user("bob", db_path=db) == 2


def test_add_user_does_not_mutate_caller_tags(db):
    tags = ["admin"]
    utility.add_user("alice", tags, db_path=db)
    assert tags == ["admin"]


def test_add_user_default_tags_do_not_accumulate(db):
    utility.add_user("alice", db_path=db)
    utility.add_user("bob", db_path=db)
    assert utility.get_user_by_name("bob", db_path=db)["tags"] == ["new"]


def test_add_user_does_not_duplicate_new_tag(db):
    utility.add_user("alice", ["new", "admin"], db_path=db)
    assert utility.get_user_by_name("alice", db_path=db)["tags"] == ["new", "admin"]


@pytest.mark.parametrize("bad_name", ["", "   ", None, 42])
def test_add_user_rejects_bad_name(db, bad_name):
    with pytest.raises(ValueError):
        utility.add_user(bad_name, db_path=db)


@pytest.mark.parametrize("name", ["O'Brien", "x'); DROP TABLE users; --", 'quote"s'])
def test_names_with_quotes_are_stored_verbatim(db, name):
    uid = utility.add_user(name, db_path=db)
    assert utility.get_user_by_name(name, db_path=db) == {
        "id": uid, "name": name, "tags": ["new"],
    }


def test_get_user_by_name_is_not_injectable(db):
    utility.add_user("alice", db_path=db)
    assert utility.get_user_by_name("nobody' OR '1'='1", db_path=db) is None


def test_get_user_by_name_missing_returns_none(db):
    assert utility.get_user_by_name("ghost", db_path=db) is None


def test_get_user_by_name_decodes_tags(db):
    utility.add_user("alice", ["admin"], db_path=db)
    assert utility.get_user_by_name("alice", db_path=db)["tags"] == ["admin", "new"]


def test_password_roundtrip(db):
    uid = utility.add_user("alice", db_path=db)
    utility.store_password(uid, "s3cret", db_path=db)
    assert utility.verify_password(uid, "s3cret", db_path=db)
    assert not utility.verify_password(uid, "wrong", db_path=db)


def test_password_is_salted_and_not_plaintext(db):
    a = utility.add_user("alice", db_path=db)
    b = utility.add_user("bob", db_path=db)
    utility.store_password(a, "same", db_path=db)
    utility.store_password(b, "same", db_path=db)
    with utility.closing(utility._connect(db)) as conn:
        hashes = [h for (h,) in conn.execute("SELECT password_hash FROM users")]
    assert hashes[0] != hashes[1]
    assert all("same" not in h and "emas" not in h for h in hashes)


def test_store_password_unknown_user(db):
    with pytest.raises(LookupError):
        utility.store_password(999, "pw", db_path=db)


def test_store_password_rejects_empty(db):
    uid = utility.add_user("alice", db_path=db)
    with pytest.raises(ValueError):
        utility.store_password(uid, "", db_path=db)


def test_verify_password_without_password_or_user(db):
    uid = utility.add_user("alice", db_path=db)
    assert not utility.verify_password(uid, "x", db_path=db)
    assert not utility.verify_password(999, "x", db_path=db)


def test_set_active_keeps_last_five_unique():
    for uid in [1, 2, 3, 2, 4, 5, 6, 7]:
        utility.set_active(uid)
    # повторная активация двигает 2 в конец, самые давние (1, 3) вытесняются
    assert utility.get_active_users() == [2, 4, 5, 6, 7]


def test_set_active_is_thread_safe():
    barrier = threading.Barrier(50)

    def worker(uid):
        barrier.wait()
        for _ in range(200):
            utility.set_active(uid)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    active = utility.get_active_users()
    assert len(active) == utility.MAX_ACTIVE_USERS
    assert len(set(active)) == len(active)
