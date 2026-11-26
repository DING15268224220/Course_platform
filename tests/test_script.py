#!/usr/bin/env python3
"""Course_platform V4 reproducible backend/frontend acceptance runner."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent
SCREENSHOT_DIR = TEST_DIR / "screenshots"
BACKEND_TEST_LOG = SCREENSHOT_DIR / "backend-tests.log"
RESULT_JSON = SCREENSHOT_DIR / "test-results.json"
LAST_RUN_REPORT = SCREENSHOT_DIR / "LAST_RUN.md"
FINAL_REPORT = TEST_DIR / "TEST_REPORT.md"

ALL_PAGES = ("overview", "projects", "teams", "submissions", "reviews", "grades", "logs")
DEMO_USERS = (
    {"id": "a1", "key": "admin", "role": "教务管理员", "pages": ("overview", "projects", "teams", "submissions", "grades", "logs")},
    {"id": "t1", "key": "teacher", "role": "教师", "pages": ALL_PAGES},
    {"id": "ta1", "key": "assistant", "role": "助教", "pages": ("overview", "projects", "teams", "submissions", "grades", "logs")},
    {"id": "s1", "key": "student", "role": "学生", "pages": ALL_PAGES},
)
PAGE_LABELS = {
    "overview": "工作台概览",
    "projects": "项目管理",
    "teams": "团队与成员",
    "submissions": "成果提交",
    "reviews": "匿名互评",
    "grades": "成绩管理",
    "logs": "操作记录",
}
BACKEND_DESCRIPTIONS = {
    "test_ac03_overdue_submission_is_rejected": "AC-03 逾期成果提交被拒绝且不生成有效记录",
    "test_ac04_trims_extremes_and_rounds_to_one_decimal": "互评去除极值并保留一位小数",
    "test_ac06_publish_snapshot_student_privacy_and_excel": "成绩发布快照、学生隐私及 Excel/PDF 导出",
    "test_assigned_review_download_uses_anonymous_route_and_filename": "匿名互评分配下载及匿名文件名",
    "test_assistant_cannot_write_teacher_score_or_see_final_score": "助教无权录入或查看教师终评分",
    "test_authentication_required_and_login": "未登录拦截、错误密码及教师登录",
    "test_grade_math": "综合成绩计算公式",
    "test_notification_can_be_marked_read": "单条通知标记已读",
    "test_other_team_file_is_not_downloadable": "学生无法直接下载其他团队文件",
    "test_peer_review_below_two_flags_warning": "互评不足两份时显示边界预警",
    "test_review_requires_assignment": "互评必须具有系统分配任务",
    "test_score_team_must_belong_to_project": "评分团队必须属于当前项目",
    "test_small_team_cannot_submit": "团队人数不足时禁止提交",
    "test_student_bootstrap_does_not_leak_other_teams": "学生数据范围不泄露其他团队信息",
    "test_student_cannot_create_project": "学生无权创建项目",
    "test_unknown_user_is_json_401": "未知用户返回规范 JSON 401",
    "test_unpublish_preserves_snapshot_history": "撤回成绩后保留历史快照",
    "test_unpublished_student_grade_is_hidden": "未发布成绩对学生隐藏",
    "test_v4_course_project_draft_and_publish": "课程创建、项目草稿及正式发布",
    "test_v4_grade_appeal_admin_resolution": "学生成绩申诉、管理员处理、审计与备份",
    "test_v4_join_request_requires_leader_approval": "入队申请必须由组长审批",
    "test_v4_login_lockout_after_five_failures": "连续五次登录失败后账号锁定",
    "test_v4_member_task_allows_designated_member_submission": "指定成员任务及成果提交权限",
    "test_v4_multidimensional_review_draft_and_alert": "三维互评、草稿及异常评分预警",
    "test_v4_process_return_and_iteration_score": "助教退回、查收及迭代过程评分",
    "test_weights_reject_invalid_range_and_sum": "评分权重范围及总和校验",
    "test_create_team_leave_and_teacher_member_adjustment": "创建/退出团队及教师例外调员",
    "test_csv_export_after_grade_publication": "成绩发布后 CSV 导出",
    "test_member_task_creation_and_status_update": "成员任务创建及状态更新",
    "test_project_update_and_add_iteration": "项目修改及新增迭代",
    "test_public_endpoints_session_notifications_and_logout": "公共接口、会话、全部已读及退出",
    "test_reminders_review_toggle_alert_resolution_and_scores": "催交、互评开关、预警处理及过程/终评分",
    "test_submission_upload_download_versions_and_withdraw": "成果上传、下载、版本历史及撤回",
}

REQUIREMENT_COVERAGE = (
    ("AC-01", "评分权重合计必须为 100%", ("test_weights_reject_invalid_range_and_sum",)),
    ("AC-02", "在线组队、申请审批与教师例外调员留痕", ("test_v4_join_request_requires_leader_approval", "test_create_team_leave_and_teacher_member_adjustment")),
    ("AC-03", "迭代截止后拒绝成果提交", ("test_ac03_overdue_submission_is_rejected",)),
    ("AC-04", "互评去除最高分和最低分后计算平均值", ("test_ac04_trims_extremes_and_rounds_to_one_decimal",)),
    ("AC-05", "助教过程检查、退回、催交与操作记录", ("test_v4_process_return_and_iteration_score", "test_reminders_review_toggle_alert_resolution_and_scores")),
    ("AC-06", "成绩加权、个人隐私、发布与撤回快照", ("test_ac06_publish_snapshot_student_privacy_and_excel", "test_unpublish_preserves_snapshot_history")),
    ("AC-07", "CSV、Excel 和 PDF 成绩导出", ("test_csv_export_after_grade_publication", "test_ac06_publish_snapshot_student_privacy_and_excel")),
    ("SEC-01", "登录锁定、角色权限及数据范围隔离", ("test_v4_login_lockout_after_five_failures", "test_student_bootstrap_does_not_leak_other_teams", "test_assistant_cannot_write_teacher_score_or_see_final_score")),
    ("AUD-01", "审计链校验与数据库备份", ("test_v4_grade_appeal_admin_resolution",)),
)


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "未安装"


def git_value(*args: str) -> str:
    root_check = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--show-toplevel"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if root_check.returncode != 0:
        return "未初始化"
    try:
        repository_root = Path(root_check.stdout.strip()).resolve()
    except OSError:
        return "未初始化"
    if repository_root != PROJECT_ROOT.resolve():
        return "未初始化"
    completed = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "未初始化"


def wait_for_service(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{base_url.rstrip('/')}/api/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=2) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (OSError, URLError) as error:
            last_error = error
        time.sleep(0.4)
    raise RuntimeError(f"测试服务未就绪：{health_url}（{last_error}）")


def parse_pytest_cases(log: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    pattern = re.compile(r"^(?P<node>\S+::\S+::test_\S+)\s+(?P<status>PASSED|FAILED|SKIPPED|ERROR)(?:\s+\[.*\])?$", re.MULTILINE)
    for index, match in enumerate(pattern.finditer(log), start=1):
        node = match.group("node")
        test_name = node.rsplit("::", 1)[-1]
        cases.append(
            {
                "id": f"BE-{index:02d}",
                "name": test_name,
                "description": BACKEND_DESCRIPTIONS.get(test_name, test_name),
                "source": node.split("::", 1)[0].replace("\\", "/"),
                "status": match.group("status"),
            }
        )
    return cases


def run_backend_tests() -> tuple[str, int, list[dict[str, str]]]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(PROJECT_ROOT / "backend" / "tests" / "test_app.py"),
        str(TEST_DIR / "test_full_api.py"),
        "-v",
        "--tb=short",
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    log = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    BACKEND_TEST_LOG.write_text(log, encoding="utf-8")
    print(log.rstrip())
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return status, completed.returncode, parse_pytest_cases(log)


def start_isolated_server(port: int, data_dir: Path) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update({"PLATFORM_DATA_DIR": str(data_dir), "PORT": str(port), "PYTHONUTF8": "1"})
    return subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "backend" / "app.py")],
        cwd=PROJECT_ROOT / "backend",
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def stop_server(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def save_screenshot(page: Any, filename: str) -> str:
    destination = SCREENSHOT_DIR / filename
    page.screenshot(path=str(destination), full_page=True)
    return f"screenshots/{filename}"


def open_login(page: Any, base_url: str) -> None:
    page.goto(base_url, wait_until="networkidle")
    page.locator("#login-form").wait_for(state="visible")
    page.locator("#login-user option").first.wait_for(state="attached")


def login(page: Any, user_id: str, password: str) -> None:
    page.locator("#login-user").select_option(user_id)
    page.locator("#login-password").fill(password)
    page.locator("#login-submit").click()


def capture_frontend_cases(page: Any, base_url: str, password: str) -> tuple[list[dict[str, str]], list[str]]:
    cases: list[dict[str, str]] = []
    errors: list[str] = []
    open_login(page, base_url)
    cases.append({"id": "FE-00", "description": "登录页加载及演示账号列表", "role": "公共", "page": "登录页", "status": "PASS", "screenshot": save_screenshot(page, "00-login-page.png")})

    login(page, "t1", "invalid-password-for-acceptance")
    error_box = page.locator("#login-error")
    error_box.wait_for(state="visible")
    invalid_status = "PASS" if error_box.inner_text().strip() else "FAIL"
    cases.append({"id": "FE-01", "description": "错误密码显示明确提示（预期异常）", "role": "教师", "page": "登录页", "status": invalid_status, "screenshot": save_screenshot(page, "01-invalid-password.png")})

    case_number = 2
    for user in DEMO_USERS:
        open_login(page, base_url)
        login(page, user["id"], password)
        page.locator("#app-shell").wait_for(state="visible")
        actual_role = page.locator("#user-role").inner_text().strip()
        role_ok = user["role"] in actual_role
        for page_index, page_key in enumerate(user["pages"], start=1):
            filename = f"{user['key']}-{page_index:02d}-{page_key}.png"
            status = "PASS"
            detail = f"{user['role']}进入{PAGE_LABELS[page_key]}页面"
            button = page.locator(f'#nav [data-page="{page_key}"]')
            if not role_ok or button.count() != 1:
                status = "FAIL"
                detail += "（角色或导航不匹配）"
            else:
                button.click()
                page.locator(f'#nav [data-page="{page_key}"][aria-current="page"]').wait_for()
                page.locator("#content").wait_for(state="visible")
                page.wait_for_timeout(150)
                if not page.locator("#content").inner_text().strip():
                    status = "FAIL"
                    detail += "（页面内容为空）"
            evidence = save_screenshot(page, filename)
            cases.append({"id": f"FE-{case_number:02d}", "description": detail, "role": user["role"], "page": PAGE_LABELS[page_key], "status": status, "screenshot": evidence})
            if status == "FAIL":
                errors.append(f"{user['role']}/{PAGE_LABELS[page_key]} 未通过")
            case_number += 1
        page.locator("#logout-btn").click()
        page.locator("#login-form").wait_for(state="visible")
    return cases, errors


def run_frontend_tests(base_url: str, password: str, headed: bool) -> tuple[str, list[dict[str, str]], list[str], str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("未安装 Playwright；请执行 python -m pip install playwright") from error

    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        browser_version = browser.version
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})

            def record_console_error(message: Any) -> None:
                if message.type == "error" and "status of 401" not in message.text:
                    errors.append(f"浏览器控制台：{message.text}")

            page.on("console", record_console_error)
            page.on("response", lambda response: errors.append(f"HTTP {response.status}: {response.url}") if response.status >= 500 else None)
            cases, case_errors = capture_frontend_cases(page, base_url, password)
            errors.extend(case_errors)
        finally:
            browser.close()
    status = "PASS" if not errors and all(case["status"] == "PASS" for case in cases) else "FAIL"
    return status, cases, errors, browser_version


def collect_environment(base_url: str, browser_version: str) -> dict[str, str]:
    # Use the interpreter that is actually running the suite. Calling an env's
    # python.exe from a terminal whose prompt still says "(base)" must not be
    # reported as the base environment.
    prefix_name = Path(sys.prefix).name
    conda_name = prefix_name if prefix_name.lower() not in ("anaconda", "miniconda", "miniconda3") else (os.environ.get("CONDA_DEFAULT_ENV") or prefix_name)
    return {
        "操作系统": platform.platform(),
        "Conda 环境": conda_name,
        "Python": platform.python_version(),
        "pytest": package_version("pytest"),
        "Flask": package_version("Flask"),
        "Playwright": package_version("playwright"),
        "Chromium": browser_version or "本次未执行前端测试",
        "Git 分支": git_value("branch", "--show-current"),
        "Git 提交": git_value("rev-parse", "--short", "HEAD"),
        "测试服务": base_url,
        "测试数据": "临时隔离数据库（不修改正式数据）",
    }


def status_counts(cases: list[dict[str, str]]) -> tuple[int, int, int]:
    return len(cases), sum(c["status"] == "PASS" or c["status"] == "PASSED" for c in cases), sum(c["status"] in ("FAIL", "FAILED", "ERROR") for c in cases)


def build_report(
    run_at: str,
    mode: str,
    backend_status: str,
    frontend_status: str,
    backend_cases: list[dict[str, str]],
    frontend_cases: list[dict[str, str]],
    errors: list[str],
    environment: dict[str, str],
) -> str:
    be_total, be_pass, be_fail = status_counts(backend_cases)
    fe_total, fe_pass, fe_fail = status_counts(frontend_cases)
    requested_statuses = [backend_status] if mode == "backend" else [frontend_status] if mode == "frontend" else [backend_status, frontend_status]
    conclusion = "PASS" if all(status == "PASS" for status in requested_statuses) else "FAIL"
    lines = [
        "# Course_platform V4 自动化测试报告",
        "",
        f"> 本报告由 `tests/test_script.py --mode {mode}` 于 {run_at} 自动生成。截图使用相对路径，可直接在 GitHub 中显示。",
        "",
        "## 1. 测试结论",
        "",
        "| 测试部分 | 状态 | 用例数 | 通过 | 失败 |",
        "| --- | --- | ---: | ---: | ---: |",
        f"| 后端与业务接口 | {backend_status} | {be_total} | {be_pass} | {be_fail} |",
        f"| 前端浏览器页面 | {frontend_status} | {fe_total} | {fe_pass} | {fe_fail} |",
        f"| **本次总结果** | **{conclusion}** | **{be_total + fe_total}** | **{be_pass + fe_pass}** | **{be_fail + fe_fail}** |",
        "",
        "## 2. 执行顺序与方法",
        "",
        "1. 后端阶段：使用 pytest 和 Flask 测试客户端，逐项测试接口、数据校验、角色权限与业务闭环。",
        "2. 前端阶段：自动启动临时测试服务，依次测试登录页、错误密码，再按“教务管理员 → 教师 → 助教 → 学生”登录。",
        "3. 每个角色按左侧导航从上到下测试全部可见页面；页面须可访问、内容非空，且不得出现 HTTP 500 或非预期控制台错误。",
        "4. 每一步前端检查均保存截图；无论 PASS 或 FAIL 都会记录状态。失败时报告保留错误信息和当时截图。",
        "",
        "后端单独运行：`python tests/test_script.py --mode backend`  ",
        "前端单独运行：`python tests/test_script.py --mode frontend`  ",
        "完整运行：`python tests/test_script.py --mode all`",
        "",
        "## 3. 测试运行环境",
        "",
        "| 项目 | 值 |",
        "| --- | --- |",
    ]
    lines.extend(f"| {key} | {value.replace('|', '/')} |" for key, value in environment.items())
    lines.extend(["", "## 4. 后端与业务接口逐项结果", ""])
    if backend_cases:
        lines.extend(["| 编号 | 状态 | 测试说明 | 来源 |", "| --- | --- | --- | --- |"])
        lines.extend(f"| {case['id']} | {case['status']} | {case['description']} | `{case['source']}` |" for case in backend_cases)
    else:
        lines.append("本次未执行后端测试。")
    lines.extend(["", "完整 pytest 日志：[`screenshots/backend-tests.log`](screenshots/backend-tests.log)", "", "### 4.1 需求分析验收追踪", ""])
    if backend_cases:
        case_by_name = {case["name"]: case for case in backend_cases}
        lines.extend(["| 需求/验收项 | 验证内容 | 关联测试 | 结果 |", "| --- | --- | --- | --- |"])
        for requirement_id, description, test_names in REQUIREMENT_COVERAGE:
            linked = [case_by_name.get(name) for name in test_names]
            status = "PASS" if all(case and case["status"] == "PASSED" for case in linked) else "FAIL"
            case_ids = "、".join(case["id"] if case else name for case, name in zip(linked, test_names))
            lines.append(f"| {requirement_id} | {description} | {case_ids} | {status} |")
    else:
        lines.append("本次未执行需求追踪所依赖的后端测试。")
    lines.extend(["", "## 5. 前端测试顺序与逐项结果", ""])
    if frontend_cases:
        lines.extend(["| 顺序 | 编号 | 角色 | 页面/检查 | 状态 | 截图证据 |", "| ---: | --- | --- | --- | --- | --- |"])
        for order, case in enumerate(frontend_cases, start=1):
            lines.append(f"| {order} | {case['id']} | {case['role']} | {case['description']} | {case['status']} | [查看截图]({case['screenshot']}) |")
    else:
        lines.append("本次未执行前端测试。")
    failed_cases = [case for case in backend_cases + frontend_cases if case["status"] in ("FAIL", "FAILED", "ERROR")]
    lines.extend(["", "## 6. 问题、失败与预期异常", ""])
    if failed_cases or errors:
        lines.append("### 实际失败或问题")
        lines.append("")
        for case in failed_cases:
            lines.append(f"- `{case['id']}` {case['description']}：{case['status']}")
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- 本次未发现实际失败用例、HTTP 500 或非预期浏览器控制台错误。")
    lines.extend([
        "- 错误密码、未知账号、越权访问、团队人数不足、非法权重、五次失败锁定等属于**预期异常测试**；系统正确拒绝这些操作时，该测试记为 PASS。",
        "- 因此报告不会把“预期收到 401/403/400”误判成产品缺陷。",
        "",
        "## 7. 前端截图证据（按实际执行顺序）",
        "",
    ])
    if frontend_cases:
        current_role = None
        for case in frontend_cases:
            if case["role"] != current_role:
                current_role = case["role"]
                lines.extend([f"### {current_role}", ""])
            lines.extend([f"#### {case['id']} · {case['description']} · {case['status']}", "", f"![{case['description']}]({case['screenshot']})", ""])
    else:
        lines.append("本次未生成前端截图。")
    return "\n".join(lines)


def write_result_files(
    mode: str,
    backend_status: str,
    frontend_status: str,
    backend_cases: list[dict[str, str]],
    frontend_cases: list[dict[str, str]],
    errors: list[str],
    environment: dict[str, str],
) -> None:
    run_at = datetime.now().astimezone().isoformat(timespec="seconds")
    result = {
        "run_at": run_at,
        "mode": mode,
        "backend_status": backend_status,
        "frontend_status": frontend_status,
        "environment": environment,
        "backend_cases": backend_cases,
        "frontend_cases": frontend_cases,
        "errors": errors,
    }
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(run_at, mode, backend_status, frontend_status, backend_cases, frontend_cases, errors, environment)
    FINAL_REPORT.write_text(report, encoding="utf-8")
    LAST_RUN_REPORT.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Course_platform V4 前后端自动化验收")
    parser.add_argument("--mode", choices=("all", "backend", "frontend"), default="all", help="分别执行后端、前端或全部测试")
    parser.add_argument("--base-url", help="前端测试使用已启动服务；省略时自动启动隔离服务")
    parser.add_argument("--port", type=int, default=5088, help="隔离测试服务端口")
    parser.add_argument("--password", default="123456", help="演示账号密码")
    parser.add_argument("--headed", action="store_true", help="显示 Chromium 窗口")
    parser.add_argument("--service-timeout", type=float, default=25.0, help="等待服务启动秒数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    backend_status = "SKIPPED"
    frontend_status = "SKIPPED"
    backend_cases: list[dict[str, str]] = []
    frontend_cases: list[dict[str, str]] = []
    errors: list[str] = []
    browser_version = ""
    server: subprocess.Popen[str] | None = None
    base_url = args.base_url.rstrip("/") if args.base_url else f"http://127.0.0.1:{args.port}"

    if args.mode in ("all", "backend"):
        print("[后端] 执行 pytest、权限与业务接口测试……")
        backend_status, return_code, backend_cases = run_backend_tests()
        if backend_status == "FAIL":
            errors.append(f"后端测试失败，pytest 退出码 {return_code}")

    if args.mode in ("all", "frontend"):
        temporary_data = tempfile.TemporaryDirectory(prefix="course-platform-acceptance-")
        try:
            if not args.base_url:
                server = start_isolated_server(args.port, Path(temporary_data.name))
            wait_for_service(base_url, args.service_timeout)
            print("[前端] 按角色和导航顺序测试全部页面并保存截图……")
            frontend_status, frontend_cases, frontend_errors, browser_version = run_frontend_tests(base_url, args.password, args.headed)
            errors.extend(frontend_errors)
        except Exception as error:
            frontend_status = "FAIL"
            errors.append(f"前端测试未完成：{error}")
        finally:
            stop_server(server)
            temporary_data.cleanup()

    environment = collect_environment(base_url, browser_version)
    write_result_files(args.mode, backend_status, frontend_status, backend_cases, frontend_cases, errors, environment)
    requested = [backend_status] if args.mode == "backend" else [frontend_status] if args.mode == "frontend" else [backend_status, frontend_status]
    passed = all(status == "PASS" for status in requested)
    print("=" * 68)
    print(f"后端与业务接口：{backend_status}（{len(backend_cases)} 项）")
    print(f"前端浏览器页面：{frontend_status}（{len(frontend_cases)} 项）")
    print(f"报告：{FINAL_REPORT}")
    print(f"截图目录：{SCREENSHOT_DIR}")
    print(f"最终结果：{'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
