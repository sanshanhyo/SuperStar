#!/usr/bin/env python3
"""Render a runtime-only config.ini from the checked-in template."""

from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path


COURSE_ID = "266120241"


def required_secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    if "\r" in value or "\n" in value:
        raise SystemExit(f"environment variable {name} must not contain a newline")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    username = required_secret("CHAOXING_USERNAME")
    password = required_secret("CHAOXING_PASSWORD")

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
    common["course_list"] = COURSE_ID
    common["speed"] = "1"
    common["jobs"] = "1"
    common["notopen_action"] = "continue"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as config_file:
        config.write(config_file)
    os.chmod(args.output, 0o600)
    print(f"generated runtime config at {args.output}")


if __name__ == "__main__":
    main()
