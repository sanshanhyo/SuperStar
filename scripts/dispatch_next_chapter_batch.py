#!/usr/bin/env python3
"""Dispatch the next batch of a successful GitHub Actions chapter chain."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

try:
    from scripts.chapter_plan import split_plan
except ModuleNotFoundError:
    from chapter_plan import split_plan


WORKFLOW_FILE = "three-chapter-automation.yml"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


def dispatch_next_batch() -> bool:
    remaining_plan = os.environ.get("REMAINING_PLAN", "").strip()
    continue_required = os.environ.get("CONTINUE_REQUIRED", "").strip().lower() == "true"
    if not remaining_plan and not continue_required:
        return False

    repository = required_env("GITHUB_REPOSITORY")
    token = required_env("GH_TOKEN")
    ref = os.environ.get("GITHUB_REF_NAME", "main").strip() or "main"
    inputs = {
        "account_id": required_env("INPUT_ACCOUNT_ID"),
        "course_id": required_env("INPUT_COURSE_ID"),
        "clazz_id": os.environ.get("INPUT_CLAZZ_ID", "").strip(),
        "chapter_selection": "",
        "chapter_plan": "",
        "auto_continue": "false",
        "start_chapter": "1",
        "end_chapter": "0",
        "video_speed": required_env("INPUT_VIDEO_SPEED"),
    }
    if remaining_plan:
        current_batch, rest = split_plan(remaining_plan, "")
        inputs["chapter_plan"] = current_batch + (f";{rest}" if rest else "")
    else:
        inputs["auto_continue"] = "true"
        inputs["start_chapter"] = required_env("NEXT_START_CHAPTER")
        inputs["end_chapter"] = required_env("INPUT_END_CHAPTER")

    payload = {
        "ref": ref,
        "inputs": inputs,
    }

    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/"
        f"{WORKFLOW_FILE}/dispatches"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "SuperStar-chapter-chain",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"工作流派发返回异常状态: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"下一批章节派发失败: HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"下一批章节派发失败: {exc.reason}") from exc

    if remaining_plan:
        print(f"已派发下一批章节: {inputs['chapter_plan'].split(';', 1)[0]}")
    else:
        print(
            "已派发自动续跑: "
            f"从第 {inputs['start_chapter']} 章继续到第 {inputs['end_chapter']} 章"
        )
    return True


def main() -> int:
    try:
        dispatch_next_batch()
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
