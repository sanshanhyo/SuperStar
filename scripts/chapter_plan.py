#!/usr/bin/env python3
"""Normalize one-off chapter selection or a semicolon-separated batch plan."""

from __future__ import annotations

import argparse
import os
import re
import sys


MAX_CHAPTERS_PER_BATCH = 3


def parse_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"布尔输入无效: {raw_value!r}")


def normalize_batch(raw_batch: str) -> str:
    """Validate one batch and return its canonical comma-separated form."""
    tokens = [token for token in re.split(r"[,，\s]+", raw_batch.strip()) if token]
    if not tokens:
        raise ValueError("章节批次不能为空")

    try:
        chapters = [int(token) for token in tokens]
    except ValueError as exc:
        raise ValueError(f"章节批次包含无效顺序号: {raw_batch!r}") from exc

    if any(chapter <= 0 for chapter in chapters):
        raise ValueError("章节顺序号必须是正整数")
    if len(chapters) > MAX_CHAPTERS_PER_BATCH:
        raise ValueError(f"每个章节批次最多只能有 {MAX_CHAPTERS_PER_BATCH} 个顺序号")
    if len(set(chapters)) != len(chapters):
        raise ValueError(f"章节批次不能重复顺序号: {raw_batch!r}")

    return ",".join(str(chapter) for chapter in chapters)


def split_plan(raw_plan: str, raw_selection: str) -> tuple[str, str]:
    """Return the current batch and the remaining plan."""
    plan = raw_plan.strip()
    selection = raw_selection.strip()
    if plan and selection:
        raise ValueError("chapter_plan 和 chapter_selection 只能填写一个")

    if not plan:
        return (normalize_batch(selection) if selection else ""), ""

    raw_batches = re.split(r"[;；]", plan)
    if any(not batch.strip() for batch in raw_batches):
        raise ValueError("chapter_plan 中不能有空批次")

    batches = [normalize_batch(batch) for batch in raw_batches]
    return batches[0], ";".join(batches[1:])


def write_outputs(current_selection: str, remaining_plan: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print(f"current_selection={current_selection}")
        print(f"remaining_plan={remaining_plan}")
        return

    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"current_selection={current_selection}\n")
        output.write(f"remaining_plan={remaining_plan}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="")
    parser.add_argument("--selection", default="")
    parser.add_argument("--auto-continue", default="false")
    args = parser.parse_args()

    try:
        if parse_bool(args.auto_continue) and (
            args.plan.strip() or args.selection.strip()
        ):
            raise ValueError(
                "auto_continue 模式不能同时填写 chapter_plan 或 chapter_selection"
            )
        current_selection, remaining_plan = split_plan(args.plan, args.selection)
        write_outputs(current_selection, remaining_plan)
    except ValueError as exc:
        print(f"章节计划无效: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
