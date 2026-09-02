#!/usr/bin/env python3
"""Render a runtime-only config.ini from the checked-in template."""

from __future__ import annotations

import argparse
import configparser
import math
import os
from pathlib import Path

try:
    from scripts.account_registry import AccountRegistryError, resolve_account
except ModuleNotFoundError:
    from account_registry import AccountRegistryError, resolve_account


COURSE_ID = "266120241"
DEFAULT_TIKU_API_ENDPOINT = "https://api.shenwenai.com/v1"
DEFAULT_TIKU_API_MODEL = "gpt-5.6-luna"
MIN_VIDEO_SPEED = 1.0
MAX_VIDEO_SPEED = 2.0


def required_secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    if "\r" in value or "\n" in value:
        raise SystemExit(f"environment variable {name} must not contain a newline")
    return value


def required_account_registry() -> str:
    value = os.environ.get("SUPERSTAR_ACCOUNTS_JSON", "")
    if not value:
        raise SystemExit("missing required environment variable: SUPERSTAR_ACCOUNTS_JSON")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help="configure the OpenAI-compatible answer provider",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="enable real quiz submission; only use for an explicit submit test",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=MIN_VIDEO_SPEED,
        help="video speed from 1.0 to 2.0",
    )
    parser.add_argument(
        "--account-id",
        default="",
        help="account alias in SUPERSTAR_ACCOUNTS_JSON",
    )
    parser.add_argument(
        "--course-id",
        default=COURSE_ID,
        help="course ID registered for the selected account",
    )
    parser.add_argument(
        "--clazz-id",
        default="",
        help="optional class ID; required when the account has multiple classes",
    )
    args = parser.parse_args()
    if args.submit and not args.enable_ai:
        raise SystemExit("--submit requires --enable-ai")
    if (
        not math.isfinite(args.speed)
        or not MIN_VIDEO_SPEED <= args.speed <= MAX_VIDEO_SPEED
    ):
        raise SystemExit(
            f"--speed must be between {MIN_VIDEO_SPEED} and {MAX_VIDEO_SPEED}"
        )

    course_id = args.course_id.strip()
    if not course_id:
        raise SystemExit("--course-id must not be empty")

    if args.account_id.strip():
        try:
            username, password, clazz_id = resolve_account(
                required_account_registry(),
                args.account_id.strip(),
                course_id,
                args.clazz_id,
            )
        except AccountRegistryError as exc:
            raise SystemExit(str(exc)) from exc
    else:
        username = required_secret("CHAOXING_USERNAME")
        password = required_secret("CHAOXING_PASSWORD")
        clazz_id = args.clazz_id.strip()

    config = configparser.ConfigParser(interpolation=None)
    if not config.read(args.template, encoding="utf-8"):
        raise SystemExit(f"template not found: {args.template}")

    if not config.has_section("common"):
        raise SystemExit("config template is missing [common]")

    common = config["common"]
    common["use_cookies"] = "false"
    common["username"] = username
    common["password"] = password
    # This is deliberately fixed so a manual run cannot broaden the scope.
    common["course_list"] = course_id
    common["target_course_id"] = course_id
    common["target_clazz_id"] = clazz_id
    common["speed"] = f"{args.speed:g}"
    common["jobs"] = "1"
    common["notopen_action"] = "continue"

    if args.enable_ai:
        api_key = required_secret("TIKU_API_KEY")
        api_endpoint = os.environ.get(
            "TIKU_API_ENDPOINT", DEFAULT_TIKU_API_ENDPOINT
        ).rstrip("/")
        if not api_endpoint.endswith("/v1"):
            api_endpoint += "/v1"
        api_model = os.environ.get("TIKU_API_MODEL", DEFAULT_TIKU_API_MODEL)
        if not config.has_section("tiku"):
            raise SystemExit("config template is missing [tiku]")
        tiku = config["tiku"]
        tiku["provider"] = "AI"
        tiku["endpoint"] = api_endpoint
        tiku["key"] = api_key
        tiku["model"] = api_model
        tiku["check_llm_connection"] = "true"
        tiku["submit"] = "true" if args.submit else "false"
        tiku["min_interval_seconds"] = "3"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as config_file:
        config.write(config_file)
    os.chmod(args.output, 0o600)
    print(f"generated runtime config at {args.output}")


if __name__ == "__main__":
    main()
