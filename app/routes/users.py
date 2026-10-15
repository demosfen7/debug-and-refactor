"""Маршруты HTTP API пользователей."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, url_for

from ..db import get_db
from ..repositories import api_users
from ..utils.validation import name_from_payload

bp = Blueprint("users", __name__)

NAME_ERROR = "field 'name' must be a non-empty string"


@bp.post("/adduser")
def add_user():
    name = name_from_payload(request.get_json(silent=True))
    if name is None:
        return jsonify(error=NAME_ERROR), 400

    user = api_users.insert_user(get_db(), name)
    return jsonify(user), 201, {"Location": url_for(".get_user", uid=user["id"])}


@bp.get("/user/<int:uid>")
def get_user(uid: int):
    user = api_users.find_user(get_db(), uid)
    if user is None:
        return jsonify(error="user not found"), 404
    return jsonify(user)
