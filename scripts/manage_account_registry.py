#!/usr/bin/env python3
"""Merge one account/course into the protected Actions account registry."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from scripts.account_payload import decrypt_payload
except ModuleNotFoundError:
    from account_payload import decrypt_payload


ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def required_text(name: str, value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} 必须是文本")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} 不能为空")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} 不能包含换行")
    return value if name == "password" else value.strip()


def load_registry(raw_registry: str) -> dict:
    if not raw_registry.strip():
        return {"version": 1, "accounts": {}}
    try:
        registry = json.loads(raw_registry)
    except json.JSONDecodeError as exc:
        raise ValueError("SUPERSTAR_ACCOUNTS_JSON 不是有效 JSON") from exc
    if not isinstance(registry, dict) or not isinstance(registry.get("accounts"), dict):
        raise ValueError('注册表必须包含 "accounts" 对象')
    registry.setdefault("version", 1)
    return registry


def merge_account(
    raw_registry: str,
    account_id: str,
    username: str,
    password: str,
    course_id: str,
    clazz_id: str,
) -> dict:
    account_id = required_text("account_id", account_id)
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ValueError("account_id 只能包含字母、数字、下划线和短横线")
    username = required_text("username", username)
    password = required_text("password", password)
    course_id = required_text("course_id", course_id)
    clazz_id = required_text("clazz_id", clazz_id, allow_empty=True)

    registry = load_registry(raw_registry)
    accounts = registry["accounts"]
    existing = accounts.get(account_id)
    if existing is None:
        existing = {"courses": {}}
    if not isinstance(existing, dict):
        raise ValueError(f"账号 {account_id!r} 的现有资料格式错误")

    courses = existing.get("courses", {})
    if not isinstance(courses, dict):
        raise ValueError(f"账号 {account_id!r} 的 courses 格式错误")

    existing["username"] = username
    existing["password"] = password
    existing["courses"] = courses
    courses[course_id] = {"clazz_id": clazz_id}
    accounts[account_id] = existing
    return registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--encrypted-payload", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = decrypt_payload(
            args.encrypted_payload,
            os.environ.get("SUPERSTAR_ACCOUNT_PRIVATE_KEY", ""),
        )
        registry = merge_account(
            raw_registry=os.environ.get("SUPERSTAR_ACCOUNTS_JSON", ""),
            account_id=payload["account_id"],
            username=payload["username"],
            password=payload["password"],
            course_id=payload["course_id"],
            clazz_id=payload["clazz_id"],
        )
        args.output.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"已合并账号 {payload['account_id']!r} 的课程 {payload['course_id']!r}；"
            "凭据未打印"
        )
    except ValueError as exc:
        print(f"账号注册表更新失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
