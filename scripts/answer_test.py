#!/usr/bin/env python3
"""Answer one quiz using an OpenAI-compatible provider."""

from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.answer import Tiku
from api.base import Account, Chaoxing
from api.logger import configure_console_logger, logger


COURSE_ID = "266120241"
CLAZZ_ID = "152038953"
POINT_ID = "1221167829"
POINT_TITLE = "1.1 国防的内涵"


def read_config(path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(path, encoding="utf-8"):
        raise RuntimeError(f"config file not found: {path}")
    for section in ("common", "tiku"):
        if not config.has_section(section):
            raise RuntimeError(f"config.ini is missing [{section}]")
    return config


def find_target_course(chaoxing: Chaoxing) -> dict:
    courses = chaoxing.get_course_list()
    matches = [
        course
        for course in courses
        if str(course.get("courseId")) == COURSE_ID
        and str(course.get("clazzId")) == CLAZZ_ID
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one target course, got {len(matches)} "
            f"for courseId={COURSE_ID}, clazzId={CLAZZ_ID}"
        )
    course = matches[0]
    logger.info(
        "[answer-test] course identification passed: courseId={} clazzId={} title={!r}",
        course.get("courseId"),
        course.get("clazzId"),
        course.get("title", ""),
    )
    return course


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--allow-submit",
        action="store_true",
        help="explicitly allow the configured quiz submission",
    )
    args = parser.parse_args()

    configure_console_logger("DEBUG")
    config = read_config(args.config)
    common = config["common"]
    tiku_config = dict(config["tiku"])
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
    if tiku_config.get("provider") != "AI":
        raise RuntimeError("answer test requires provider=AI")
    submit_enabled = tiku_config.get("submit", "false").strip().lower() == "true"
    if submit_enabled and not args.allow_submit:
        raise RuntimeError(
            "submit=true requires the explicit --allow-submit switch"
        )

    logger.info(
        "[answer-test] scope locked to courseId={} clazzId={} pointId={} title={!r}",
        COURSE_ID,
        CLAZZ_ID,
        POINT_ID,
        POINT_TITLE,
    )
    logger.info(
        "[answer-test] submit={}: {}",
        str(submit_enabled).lower(),
        (
            "this run may submit one quiz"
            if submit_enabled
            else "answers may be saved as a draft, but the quiz will not be submitted"
        ),
    )
    logger.info(
        "[answer-test] provider=AI endpoint={} model={}",
        tiku_config.get("endpoint", ""),
        tiku_config.get("model", ""),
    )

    tiku = Tiku()
    tiku.config_set(tiku_config)
    tiku = tiku.get_tiku_from_config()
    tiku.init_tiku()
    if tiku.DISABLE:
        raise RuntimeError("AI answer provider was disabled during initialization")
    if not tiku.check_llm_connection():
        raise RuntimeError("OpenAI-compatible API connection check failed")
    logger.info("[answer-test] API connection check passed")

    chaoxing = Chaoxing(
        account=Account(username, password),
        tiku=tiku,
        query_delay=float(tiku_config.get("delay", 0)),
    )
    login_state = chaoxing.login(login_with_cookies=False)
    if not login_state.get("status"):
        raise RuntimeError(f"login failed: {login_state.get('msg', 'unknown error')}")
    logger.info("[answer-test] login check passed")

    course = find_target_course(chaoxing)
    point_data = chaoxing.get_course_point(
        COURSE_ID,
        CLAZZ_ID,
        course.get("cpi", ""),
    )
    points = point_data.get("points") if isinstance(point_data, dict) else None
    if not isinstance(points, list):
        raise RuntimeError("chapter response did not contain a points list")
    target_points = [
        point
        for point in points
        if str(point.get("id")) == POINT_ID and point.get("title") == POINT_TITLE
    ]
    if len(target_points) != 1:
        raise RuntimeError(
            f"target chapter not found exactly once: pointId={POINT_ID}, "
            f"title={POINT_TITLE!r}, matches={len(target_points)}"
        )
    point = target_points[0]

    jobs, job_info = chaoxing.get_job_list(
        course,
        point,
        report_empty_page=False,
    )
    if job_info.get("notOpen", False):
        raise RuntimeError("target chapter is not open")
    work_jobs = [job for job in jobs if job.get("type") == "workid"]
    if len(work_jobs) != 1:
        raise RuntimeError(
            f"expected exactly one quiz task in target chapter, got {len(work_jobs)}; "
            f"task_types={[job.get('type') for job in jobs]}"
        )
    work_job = work_jobs[0]
    logger.info(
        "[answer-test] selected exactly one quiz task: jobId={}",
        work_job.get("jobid", ""),
    )

    result = chaoxing.study_work(course, work_job, job_info)
    if not result.is_success():
        raise RuntimeError(f"save-only answer task failed with result={result.name}")

    logger.info(
        "[answer-test] SUCCESS: one quiz answered in submit={} mode",
        str(submit_enabled).lower(),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("[answer-test] FAILED")
        raise
