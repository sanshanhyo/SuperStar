#!/usr/bin/env python3
"""Process at most three selected or unfinished chapters for one account/course."""

from __future__ import annotations

import argparse
import configparser
import math
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.answer import Tiku
from api.base import Account, Chaoxing, StudyResult
from api.logger import configure_console_logger, logger


MAX_CHAPTERS = 3
MIN_VIDEO_SPEED = 1.0
MAX_VIDEO_SPEED = 2.0


def read_config(path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(path, encoding="utf-8"):
        raise RuntimeError(f"config file not found: {path}")
    for section in ("common", "tiku"):
        if not config.has_section(section):
            raise RuntimeError(f"config.ini is missing [{section}]")
    return config


def find_target_course(
    chaoxing: Chaoxing,
    course_id: str,
    clazz_id: str = "",
) -> dict:
    courses = chaoxing.get_course_list()
    course_matches = [
        course
        for course in courses
        if str(course.get("courseId")) == course_id
    ]
    matches = [
        course
        for course in course_matches
        if not clazz_id or str(course.get("clazzId")) == clazz_id
    ]
    if len(matches) != 1:
        available_classes = sorted(
            {str(course.get("clazzId")) for course in course_matches}
        )
        class_hint = f", clazz_id={clazz_id}" if clazz_id else ""
        raise RuntimeError(
            f"expected exactly one target course, got {len(matches)} "
            f"for courseId={course_id}{class_hint}; "
            f"available clazz_ids={available_classes}"
        )
    return matches[0]


def select_chapters(
    points: list[dict],
    raw_selection: str,
    start_chapter: int = 1,
    end_chapter: int | None = None,
) -> list[tuple[int, dict]]:
    """Select chapters by 1-based course order or take the first unfinished ones."""
    raw_selection = raw_selection.strip()

    if not raw_selection:
        return [
            (index, point)
            for index, point in enumerate(points, start=1)
            if start_chapter <= index <= (end_chapter or len(points))
            and not point.get("has_finished", False)
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
        if index < start_chapter or (end_chapter is not None and index > end_chapter):
            raise RuntimeError(
                f"章节顺序号不在允许范围：{index}，"
                f"当前范围为 {start_chapter} 到 {end_chapter or len(points)}"
            )
        selected.append((index, points[index - 1]))
    return selected


def parse_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise RuntimeError(f"布尔输入无效: {raw_value!r}")


def write_github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        logger.info("[three-chapter] output {}={}", name, value)
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def run_video(
    chaoxing: Chaoxing,
    course: dict,
    job: dict,
    job_info: dict,
    video_speed: float,
) -> None:
    result = chaoxing.study_video(
        course,
        job,
        job_info,
        _speed=video_speed,
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
        _speed=video_speed,
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
        "--course-id",
        default="",
        help="course ID; defaults to target_course_id in config.ini",
    )
    parser.add_argument(
        "--clazz-id",
        default="",
        help="optional class ID; defaults to target_clazz_id in config.ini",
    )
    parser.add_argument(
        "--chapter-selection",
        default="",
        help="章节顺序号，例如 4,5,6；留空则自动选择前三个未完成章节",
    )
    parser.add_argument(
        "--auto-continue",
        default="false",
        help="成功后由工作流自动启动下一批未完成章节",
    )
    parser.add_argument(
        "--start-chapter",
        default="1",
        help="自动续跑的起始章节顺序号，默认从第 1 章检查",
    )
    parser.add_argument(
        "--end-chapter",
        default="0",
        help="自动续跑的结束章节顺序号，0 表示课程最后一章",
    )
    args = parser.parse_args()

    auto_continue = parse_bool(args.auto_continue)
    try:
        start_chapter = int(args.start_chapter)
        end_chapter_input = int(args.end_chapter)
    except ValueError as exc:
        raise RuntimeError("start-chapter 和 end-chapter 必须是整数") from exc
    if start_chapter < 1:
        raise RuntimeError("start-chapter 必须是正整数")
    if end_chapter_input < 0:
        raise RuntimeError("end-chapter 只能是 0 或正整数")
    if auto_continue and args.chapter_selection.strip():
        raise RuntimeError(
            "auto_continue 模式不能同时填写 chapter_selection；"
            "请使用 start_chapter 指定起点"
        )

    configure_console_logger("DEBUG")
    config = read_config(args.config)
    common = config["common"]
    tiku_config = dict(config["tiku"])
    configured_courses = [
        item.strip()
        for item in common.get("course_list", "").split(",")
        if item.strip()
    ]
    course_id = (
        args.course_id.strip()
        or common.get("target_course_id", "").strip()
        or (configured_courses[0] if len(configured_courses) == 1 else "")
    )
    clazz_id = args.clazz_id.strip() or common.get("target_clazz_id", "").strip()
    if not course_id:
        raise RuntimeError("config.ini does not contain a unique target course ID")
    try:
        video_speed = float(common.get("speed", MIN_VIDEO_SPEED))
    except ValueError as exc:
        raise RuntimeError("config.ini contains an invalid video speed") from exc
    if (
        not math.isfinite(video_speed)
        or not MIN_VIDEO_SPEED <= video_speed <= MAX_VIDEO_SPEED
    ):
        raise RuntimeError(
            f"video speed must be between {MIN_VIDEO_SPEED} and {MAX_VIDEO_SPEED}"
        )
    username = common.get("username", "").strip()
    password = common.get("password", "")
    if not username or not password:
        raise RuntimeError("config.ini does not contain runtime credentials")
    if configured_courses != [course_id]:
        raise RuntimeError(
            f"course scope violation: expected only {course_id}, "
            f"got {configured_courses!r}"
        )
    if tiku_config.get("provider") != "AI":
        raise RuntimeError("three-chapter automation requires provider=AI")
    if tiku_config.get("submit", "false").strip().lower() != "true":
        raise RuntimeError("three-chapter automation requires submit=true")

    logger.info(
        "[three-chapter] scope locked to courseId={} clazzId={}, "
        "max_chapters={}, video_speed={}x",
        course_id,
        clazz_id or "auto",
        MAX_CHAPTERS,
        video_speed,
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

    course = find_target_course(chaoxing, course_id, clazz_id)
    course_id = str(course.get("courseId"))
    clazz_id = str(course.get("clazzId"))
    logger.info(
        "[three-chapter] course identification passed: courseId={} clazzId={} title={!r}",
        course_id,
        clazz_id,
        course.get("title", ""),
    )
    point_data = chaoxing.get_course_point(
        course_id,
        clazz_id,
        course.get("cpi", ""),
    )
    points = point_data.get("points") if isinstance(point_data, dict) else None
    if not isinstance(points, list) or not points:
        raise RuntimeError(
            "expected at least one chapter point, got "
            f"{len(points) if isinstance(points, list) else 'invalid response'}"
        )

    end_chapter = end_chapter_input or len(points)
    if end_chapter > len(points):
        raise RuntimeError(
            f"end-chapter 超出范围：{end_chapter}，当前课程共有 {len(points)} 个章节"
        )
    if start_chapter > end_chapter:
        raise RuntimeError(
            f"start-chapter 不能大于 end-chapter：{start_chapter} > {end_chapter}"
        )

    selected_chapters = select_chapters(
        points,
        args.chapter_selection,
        start_chapter=start_chapter if auto_continue else 1,
        end_chapter=end_chapter if auto_continue else None,
    )
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
                run_video(chaoxing, course, job, job_info, video_speed)
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

    continue_required = False
    next_start_chapter = start_chapter
    if auto_continue and selected_chapters:
        next_start_chapter = max(index for index, _ in selected_chapters) + 1
        refreshed_point_data = chaoxing.get_course_point(
            course_id,
            clazz_id,
            course.get("cpi", ""),
        )
        refreshed_points = (
            refreshed_point_data.get("points")
            if isinstance(refreshed_point_data, dict)
            else None
        )
        if not isinstance(refreshed_points, list):
            raise RuntimeError("刷新章节状态失败，无法判断是否继续自动续跑")
        continue_required = any(
            not point.get("has_finished", False)
            for index, point in enumerate(refreshed_points, start=1)
            if next_start_chapter <= index <= end_chapter
        )
        logger.info(
            "[three-chapter] auto-continue check: next_start={}, end={}, continue={}",
            next_start_chapter,
            end_chapter,
            continue_required,
        )

    write_github_output("continue_required", str(continue_required).lower())
    write_github_output("next_start_chapter", str(next_start_chapter))
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
