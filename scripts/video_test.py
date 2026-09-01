#!/usr/bin/env python3
"""Run exactly one video task as a state-changing smoke test."""

from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.base import Account, Chaoxing
from api.logger import configure_console_logger, logger


COURSE_ID = "266120241"
CLAZZ_ID = "152038953"
POINT_ID = "1221167829"
POINT_TITLE = "1.1 国防的内涵"


def read_common_config(path: Path) -> configparser.SectionProxy:
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(path, encoding="utf-8"):
        raise RuntimeError(f"config file not found: {path}")
    if not config.has_section("common"):
        raise RuntimeError("config.ini is missing [common]")
    return config["common"]


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
        "[video-test] course identification passed: courseId={} clazzId={} title={!r}",
        course.get("courseId"),
        course.get("clazzId"),
        course.get("title", ""),
    )
    return course


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

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
        "[video-test] scope locked to courseId={} clazzId={} pointId={} title={!r}",
        COURSE_ID,
        CLAZZ_ID,
        POINT_ID,
        POINT_TITLE,
    )
    logger.info(
        "[video-test] this run may update video progress, but will not call "
        "answer, work, sign-in, or submission methods"
    )

    chaoxing = Chaoxing(account=Account(username, password), tiku=None)
    login_state = chaoxing.login(login_with_cookies=False)
    if not login_state.get("status"):
        raise RuntimeError(f"login failed: {login_state.get('msg', 'unknown error')}")
    logger.info("[video-test] login check passed")

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
    logger.info(
        "[video-test] chapter identification passed: id={} title={!r} finished={} jobCount={}",
        point.get("id"),
        point.get("title", ""),
        point.get("has_finished", False),
        point.get("jobCount", ""),
    )

    jobs, job_info = chaoxing.get_job_list(
        course,
        point,
        report_empty_page=False,
    )
    if job_info.get("notOpen", False):
        raise RuntimeError("target chapter is not open")
    video_jobs = [job for job in jobs if job.get("type") == "video"]
    if len(video_jobs) != 1:
        raise RuntimeError(
            f"expected exactly one video task in target chapter, got {len(video_jobs)}; "
            f"task_types={[job.get('type') for job in jobs]}"
        )

    video_job = video_jobs[0]
    logger.info(
        "[video-test] selected exactly one video task: jobId={} name={!r} playTime={}",
        video_job.get("jobid", ""),
        video_job.get("name", ""),
        video_job.get("playTime", ""),
    )
    result = chaoxing.study_video(
        course,
        video_job,
        job_info,
        _speed=1.0,
        _type="Video",
    )
    if not result.is_success():
        raise RuntimeError(f"video task failed with result={result.name}")

    logger.info("[video-test] SUCCESS: one video task completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("[video-test] FAILED")
        raise
