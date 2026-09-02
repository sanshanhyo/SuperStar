#!/usr/bin/env python3
"""Process at most three selected or unfinished chapters of one fixed course."""

from __future__ import annotations

import argparse
import configparser
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.answer import Tiku
from api.base import Account, Chaoxing, StudyResult
from api.logger import configure_console_logger, logger


COURSE_ID = "266120241"
CLAZZ_ID = "152038953"
MAX_CHAPTERS = 3


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
        "[three-chapter] course identification passed: courseId={} clazzId={} title={!r}",
        course.get("courseId"),
        course.get("clazzId"),
        course.get("title", ""),
    )
    return course


def select_chapters(
    points: list[dict],
    raw_selection: str,
) -> list[tuple[int, dict]]:
    """Select chapters by 1-based course order or take the first unfinished ones."""
    raw_selection = raw_selection.strip()

    if not raw_selection:
        return [
            (index, point)
            for index, point in enumerate(points, start=1)
            if not point.get("has_finished", False)
        ][:MAX_CHAPTERS]

    try:
        indices = [
            int(item)
            for item in re.split(r"[,，\s]+", raw_selection)
            if item.strip()
        ]
    except ValueError as exc:
        raise RuntimeError(
            "chapter-selection 必须是章节顺序号，例如 4,5,6，"
            f"实际为 {raw_selection!r}"
        ) from exc

    if not indices:
        raise RuntimeError("chapter-selection 不能为空白字符")
    if len(indices) > MAX_CHAPTERS:
        raise RuntimeError(
            f"chapter-selection 最多选择 {MAX_CHAPTERS} 个章节"
        )
    if len(set(indices)) != len(indices):
        raise RuntimeError("chapter-selection 中不能有重复章节")

    selected = []
    for index in indices:
        if index < 1 or index > len(points):
            raise RuntimeError(
                f"章节顺序号超出范围：{index}，当前课程共有 {len(points)} 个章节"
            )
        selected.append((index, points[index - 1]))
    return selected


def run_video(chaoxing: Chaoxing, course: dict, job: dict, job_info: dict) -> None:
    result = chaoxing.study_video(
        course,
        job,
        job_info,
        _speed=1.0,
        _type="Video",
    )
    if result.is_success():
        return
    logger.warning(
        "[three-chapter] Video mode failed for jobId={}, retrying as Audio",
        job.get("jobid", ""),
    )
    result = chaoxing.study_video(
        course,
        job,
        job_info,
        _speed=1.0,
        _type="Audio",
    )
    if not result.is_success():
        raise RuntimeError(
            f"video/audio task failed: jobId={job.get('jobid', '')}, result={result.name}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--chapter-selection",
        default="",
        help="章节顺序号，例如 4,5,6；留空则自动选择前三个未完成章节",
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
        raise RuntimeError("three-chapter automation requires provider=AI")
    if tiku_config.get("submit", "false").strip().lower() != "true":
        raise RuntimeError("three-chapter automation requires submit=true")

    logger.info(
        "[three-chapter] scope locked to courseId={} clazzId={}, max_chapters={}",
        COURSE_ID,
        CLAZZ_ID,
        MAX_CHAPTERS,
    )
    logger.warning(
        "[three-chapter] state-changing run: videos and quiz submissions are enabled; "
        "chapters and tasks will be processed serially"
    )

    tiku = Tiku()
    tiku.config_set(tiku_config)
    tiku = tiku.get_tiku_from_config()
    tiku.init_tiku()
    if tiku.DISABLE:
        raise RuntimeError("AI answer provider was disabled during initialization")
    if not tiku.check_llm_connection():
        raise RuntimeError("OpenAI-compatible API connection check failed")
    logger.info("[three-chapter] API connection check passed")

    chaoxing = Chaoxing(
        account=Account(username, password),
        tiku=tiku,
        query_delay=float(tiku_config.get("delay", 0)),
    )
    login_state = chaoxing.login(login_with_cookies=False)
    if not login_state.get("status"):
        raise RuntimeError(f"login failed: {login_state.get('msg', 'unknown error')}")
    logger.info("[three-chapter] login check passed")

    course = find_target_course(chaoxing)
    point_data = chaoxing.get_course_point(
        COURSE_ID,
        CLAZZ_ID,
        course.get("cpi", ""),
    )
    points = point_data.get("points") if isinstance(point_data, dict) else None
    if not isinstance(points, list) or not points:
        raise RuntimeError(
            "expected at least one chapter point, got "
            f"{len(points) if isinstance(points, list) else 'invalid response'}"
        )

    selected_chapters = select_chapters(points, args.chapter_selection)
    if not selected_chapters:
        logger.info("[three-chapter] no unfinished chapters selected; nothing to do")

    processed_chapters = 0
    skipped_chapters = 0
    processed_tasks = 0
    for selected_index, (chapter_index, point) in enumerate(
        selected_chapters,
        start=1,
    ):
        logger.info(
            "[three-chapter] selected chapter {}/{} (course order {}): "
            "id={} title={!r} finished={} jobCount={}",
            selected_index,
            len(selected_chapters),
            chapter_index,
            point.get("id"),
            point.get("title", ""),
            point.get("has_finished", False),
            point.get("jobCount", ""),
        )
        if point.get("has_finished", False):
            logger.info("[three-chapter] chapter already finished; skipping")
            skipped_chapters += 1
            continue

        jobs, job_info = chaoxing.get_job_list(
            course,
            point,
            report_empty_page=False,
        )
        if job_info.get("notOpen", False):
            raise RuntimeError(
                f"chapter is not open: index={chapter_index}, id={point.get('id')}"
            )
        if not jobs:
            raise RuntimeError(
                f"unfinished chapter returned no task cards: id={point.get('id')}"
            )

        for job_index, job in enumerate(jobs, start=1):
            job_type = job.get("type")
            logger.info(
                "[three-chapter] selected chapter {}/{} (course order {}) "
                "task {}/{}: type={} jobId={}",
                selected_index,
                len(selected_chapters),
                chapter_index,
                job_index,
                len(jobs),
                job_type,
                job.get("jobid", ""),
            )
            if job_type == "video":
                run_video(chaoxing, course, job, job_info)
            elif job_type == "workid":
                result = chaoxing.study_work(course, job, job_info)
                if not result.is_success():
                    raise RuntimeError(
                        f"quiz task failed: jobId={job.get('jobid', '')}, result={result.name}"
                    )
            else:
                raise RuntimeError(
                    f"unsupported task type in bounded automation: {job_type!r}"
                )
            processed_tasks += 1
            logger.info(
                "[three-chapter] task completed: chapter={!r} type={} jobId={}",
                point.get("title", ""),
                job_type,
                job.get("jobid", ""),
            )
        processed_chapters += 1

    logger.info(
        "[three-chapter] SUCCESS: processed_chapters={} skipped_chapters={} processed_tasks={}",
        processed_chapters,
        skipped_chapters,
        processed_tasks,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("[three-chapter] FAILED")
        raise
