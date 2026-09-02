#!/usr/bin/env python3
"""Read the single protected multi-account registry used by Actions."""

from __future__ import annotations

import json
from typing import Any


class AccountRegistryError(RuntimeError):
    """Raised when the account registry is missing or malformed."""


def resolve_account(
    raw_registry: str,
    account_id: str,
    course_id: str,
    requested_clazz_id: str = "",
) -> tuple[str, str, str]:
    """Resolve credentials and the registered class for one account/course."""
    try:
        registry = json.loads(raw_registry)
    except json.JSONDecodeError as exc:
        raise AccountRegistryError("SUPERSTAR_ACCOUNTS_JSON is not valid JSON") from exc

    if not isinstance(registry, dict) or not isinstance(registry.get("accounts"), dict):
        raise AccountRegistryError(
            'account registry must contain an "accounts" object'
        )

    account = registry["accounts"].get(account_id)
    if not isinstance(account, dict):
        raise AccountRegistryError(f"unknown account_id: {account_id!r}")

    username = account.get("username")
    password = account.get("password")
    if not isinstance(username, str) or not username:
        raise AccountRegistryError(f"account {account_id!r} has no username")
    if not isinstance(password, str) or not password:
        raise AccountRegistryError(f"account {account_id!r} has no password")
    if "\n" in username or "\r" in username or "\n" in password or "\r" in password:
        raise AccountRegistryError(
            f"account {account_id!r} credentials must not contain newlines"
        )

    courses = account.get("courses")
    if not isinstance(courses, dict) or course_id not in courses:
        raise AccountRegistryError(
            f"course {course_id!r} is not registered for account {account_id!r}"
        )

    course_entry: Any = courses[course_id]
    registered_clazz_id = ""
    if isinstance(course_entry, dict):
        value = course_entry.get("clazz_id", "")
        if value is not None:
            registered_clazz_id = str(value).strip()
    elif isinstance(course_entry, str):
        registered_clazz_id = course_entry.strip()
    else:
        raise AccountRegistryError(
            f"course entry for {course_id!r} must be an object or class-id string"
        )

    requested_clazz_id = requested_clazz_id.strip()
    if (
        requested_clazz_id
        and registered_clazz_id
        and requested_clazz_id != registered_clazz_id
    ):
        raise AccountRegistryError(
            f"requested clazz_id {requested_clazz_id!r} does not match "
            f"registered clazz_id {registered_clazz_id!r}"
        )

    return username, password, requested_clazz_id or registered_clazz_id
