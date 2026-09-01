#!/usr/bin/env python3
"""Read-only login/course/chapter/task-card smoke test for one course."""

from __future__ import annotations

import argparse
import configparser
from collections import Counter
from pathlib import Path

from api.base import Account, Chaoxing
from api.logger import configure_console_logger, logger


COURSE_ID = "266120241"
CLAZZ_ID = "152038953"


def read_common_config(path: Path) -> configparser.SectionProxy:
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(path, encoding="utf-8"):
        raise RuntimeError(f"config file not found: {path}")
    if not config.has_section("common"):
        raise RuntimeError("config.ini is missing [common]")
    return config["common"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--max-chapters",
        type=int,
        default=3,
        help="maximum number of chapter points to inspect (default: 3)",
    )
    args = parser.parse_args()
    if args.max_chapters < 1:
        parser.error("--max-chapters must be at least 1")

    configure_console_logger("DEBUG")
    common = read_common_config(args.config)
    username = common.get("username", "").strip()
    password = common.get("password", "")
    configured_courses = [
        item.strip()
        for item in common.get("course_list", "").split(",")
        if item.strip()
    ]

    if not username or not password:
        raise RuntimeError("config.ini does not contain runtime credentials")
    if configured_courses != [COURSE_ID]:
        raise RuntimeError(
            f"course scope violation: expected only {COURSE_ID}, "
            f"got {configured_courses!r}"
        )

    logger.info(
        "[smoke] scope locked to courseId={} clazzId={}, max_chapters={}",
        COURSE_ID,
        CLAZZ_ID,
        args.max_chapters,
    )
    logger.info("[smoke] no study, answer, sign-in, or submission methods will be called")

    chaoxing = Chaoxing(account=Account(username, password), tiku=None)
    login_state = chaoxing.login(login_with_cookies=False)
    if not login_state.get("status"):
        raise RuntimeError(f"login failed: {login_state.get('msg', 'unknown error')}")
    logger.info("[smoke] login check passed")

    all_courses = chaoxing.get_course_list()
    logger.info("[smoke] course list loaded: {} entries", len(all_courses))

    course_id_matches = [
        course
        for course in all_courses
        if str(course.get("courseId")) == COURSE_ID
    ]
    target_courses = [
        course
        for course in course_id_matches
        if str(course.get("clazzId")) == CLAZZ_ID
    ]
    if not target_courses:
        available_classes = sorted(
            {str(course.get("clazzId")) for course in course_id_matches}
        )
        raise RuntimeError(
            f"target course/class not found: courseId={COURSE_ID}, "
            f"clazzId={CLAZZ_ID}; available clazzIds={available_classes}"
        )
    if len(target_courses) > 1:
        raise RuntimeError("target course/class matched more than once")

    course = target_courses[0]
    logger.info(
        "[smoke] course identification passed: courseId={} clazzId={} title={!r}",
        course.get("courseId"),
        course.get("clazzId"),
        course.get("title", ""),
    )

    point_data = chaoxing.get_course_point(
        COURSE_ID,
        CLAZZ_ID,
        course.get("cpi", ""),
    )
    points = point_data.get("points") if isinstance(point_data, dict) else None
    if not isinstance(points, list):
        raise RuntimeError("chapter response did not contain a points list")
    logger.info(
        "[smoke] chapter identification passed: {} points, hasLocked={}",
        len(points),
        point_data.get("hasLocked", False),
    )

    sampled_points = points[: args.max_chapters]
    type_counts: Counter[str] = Counter()
    for index, point in enumerate(sampled_points, start=1):
        logger.info(
            "[smoke] chapter {}/{}: id={} title={!r} finished={} need_unlock={} jobCount={}",
            index,
            len(sampled_points),
            point.get("id"),
            point.get("title", ""),
            point.get("has_finished", False),
            point.get("need_unlock", False),
            point.get("jobCount", ""),
        )
        jobs, job_info = chaoxing.get_job_list(
            course,
            point,
            report_empty_page=False,
        )
        if job_info.get("notOpen", False):
            logger.info("[smoke] chapter is not open; task-card probe skipped")
            continue
        for job in jobs:
            job_type = str(job.get("type", "unknown"))
            type_counts[job_type] += 1
            logger.info(
                "[smoke] task type identified: chapter={!r} type={} jobId={}",
                point.get("title", ""),
                job_type,
                job.get("jobid", ""),
            )

    logger.info(
        "[smoke] task-card identification passed: sampled_chapters={} type_counts={}",
        len(sampled_points),
        dict(type_counts),
    )
    if not type_counts:
        logger.warning(
            "[smoke] no uncompleted task types were returned in the sample; "
            "the card endpoint was readable, but type coverage is unavailable "
            "for already-completed or unopened chapters"
        )
    logger.info("[smoke] SUCCESS: read-only checks completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("[smoke] FAILED")
        raise
