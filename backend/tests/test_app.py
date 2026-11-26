import io
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as platform_app


class PlatformTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        platform_app.DATA_DIR = root / "data"
        platform_app.UPLOAD_DIR = root / "uploads"
        platform_app.DB_PATH = platform_app.DATA_DIR / "platform.db"
        platform_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        with platform_app.app.app_context():
            platform_app.init_db()
        self.client = platform_app.app.test_client()
        self.csrf = None

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, user_id="t1", password="123456"):
        response = self.client.post("/api/login", json={"user_id": user_id, "password": password})
        if response.status_code == 200:
            self.csrf = response.get_json()["csrf_token"]
        return response

    def post(self, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-CSRF-Token"] = self.csrf or ""
        return self.client.post(path, headers=headers, **kwargs)

    def test_authentication_required_and_login(self):
        self.assertEqual(self.client.get("/api/bootstrap").status_code, 401)
        self.assertEqual(self.login("t1", "wrong").status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["current_user"]["role"], "teacher")

    def test_unknown_user_is_json_401(self):
        response = self.login("missing")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["ok"])

    def test_weights_reject_invalid_range_and_sum(self):
        self.login()
        base = {
            "title": "权重校验项目",
            "description": "测试",
            "team_deadline": "2026-11-01 00:00:00",
            "overall_deadline": "2026-12-01 00:00:00",
            "review_deadline": "2026-11-25 00:00:00",
        }
        response = self.post("/api/projects", json={**base, "peer_weight": -10, "process_weight": 60, "final_weight": 50})
        self.assertEqual(response.status_code, 400)
        response = self.post("/api/projects", json={**base, "peer_weight": 20, "process_weight": 20, "final_weight": 50})
        self.assertEqual(response.status_code, 400)

    def test_student_cannot_create_project(self):
        self.login("s1")
        self.assertEqual(self.post("/api/projects", json={}).status_code, 403)

    def test_unpublished_student_grade_is_hidden(self):
        self.login("s1")
        data = self.client.get("/api/bootstrap").get_json()
        self.assertFalse(data["projects"][0]["grades_published"])
        self.assertEqual(data["projects"][0]["gradebook"], [])
        self.assertTrue(all(item["team_id"] == data["my_team"]["id"] for item in data["submissions"]))

    def test_student_bootstrap_does_not_leak_other_teams(self):
        self.login("s1")
        data = self.client.get("/api/bootstrap").get_json()
        self.assertEqual([team["id"] for team in data["teams"]], [data["my_team"]["id"]])
        self.assertTrue(data["review_targets"])
        self.assertEqual(len({item["name"] for item in data["review_targets"]}), len(data["review_targets"]))
        for item in data["review_targets"]:
            self.assertIn("assignment_id", item)
            self.assertNotIn("target_team_id", item)
            self.assertNotIn("team_name", item)

    def test_grade_math(self):
        with platform_app.app.app_context():
            grades = platform_app.gradebook(1)
        code_team = next(item for item in grades if item["team_name"] == "代码之神")
        self.assertEqual(code_team["total"], 89.75)

    def test_ac04_trims_extremes_and_rounds_to_one_decimal(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM peer_reviews WHERE project_id=1 AND target_team_id=1")
            for reviewer, score in zip(("s3", "s4", "s5", "s6", "s7"), (100, 90, 80, 60, 0)):
                db.execute(
                    "INSERT INTO peer_reviews(project_id,reviewer_id,target_team_id,score,comment,created_at) VALUES(?,?,?,?,?,?)",
                    (1, reviewer, 1, score, "AC-04", platform_app.now_iso()),
                )
            db.commit()
            grade = next(item for item in platform_app.live_gradebook(1) if item["team_id"] == 1)
        self.assertEqual(grade["peer_score"], 76.7)

    def test_peer_review_below_two_flags_warning(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM peer_reviews WHERE project_id=1 AND target_team_id=1")
            db.execute(
                "INSERT INTO peer_reviews(project_id,reviewer_id,target_team_id,score,comment,created_at) VALUES(?,?,?,?,?,?)",
                (1, "s3", 1, 85, "不足2份边界", platform_app.now_iso()),
            )
            db.commit()
            grade = next(item for item in platform_app.live_gradebook(1) if item["team_id"] == 1)
        self.assertIsNone(grade["peer_score"])
        self.assertEqual(grade["peer_count"], 1)
        self.assertIsNotNone(grade["peer_warning"])
        self.assertIn("不足2份", grade["peer_warning"])

    def test_small_team_cannot_submit(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM team_members WHERE team_id=1 AND user_id='s9'")
            db.execute("UPDATE projects SET team_deadline='2026-12-01 23:59:00' WHERE id=1")
            db.execute("UPDATE projects SET review_open=0 WHERE id=1")
            db.commit()
        self.login("s1")
        response = self.post(
            "/api/submissions/1",
            data={"file": (io.BytesIO(b"%PDF-1.7\n%%EOF"), "valid.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("3", response.get_json()["message"])

    def test_other_team_file_is_not_downloadable(self):
        other_file = Path(self.temp_dir.name) / "other.pdf"
        other_file.write_bytes(b"%PDF-1.7\n%%EOF")
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE submissions SET file_path=? WHERE team_id=2", (str(other_file),))
            db.execute("DELETE FROM review_assignments WHERE project_id=1 AND reviewer_id='s9' AND target_team_id=2")
            db.commit()
        self.login("s9")
        response = self.client.get("/api/submissions/2/download")
        self.assertEqual(response.status_code, 403)
        response.close()

    def test_review_requires_assignment(self):
        self.login("s9")
        response = self.post("/api/reviews", json={"project_id": 1, "assignment_id": "not-assigned", "score": 88, "comment": "结构清晰"})
        self.assertEqual(response.status_code, 403)

    def test_assigned_review_download_uses_anonymous_route_and_filename(self):
        assigned_file = Path(self.temp_dir.name) / "飞鹰队-成果.pdf"
        assigned_file.write_bytes(b"%PDF-1.7\n%%EOF")
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE submissions SET file_path=?,file_name=? WHERE team_id=2", (str(assigned_file), assigned_file.name))
            assignment_key = platform_app.row(
                "SELECT assignment_key FROM review_assignments WHERE project_id=1 AND reviewer_id='s9' AND target_team_id=2"
            )["assignment_key"]
            db.commit()
        self.login("s9")
        direct = self.client.get("/api/submissions/2/download")
        self.assertEqual(direct.status_code, 403)
        direct.close()
        tasks = self.client.get("/api/bootstrap").get_json()["review_targets"]
        self.assertIn(assignment_key, {task["assignment_id"] for task in tasks})
        response = self.client.get(f"/api/review-assignments/{assignment_key}/download")
        self.assertEqual(response.status_code, 200)
        self.assertIn("anonymous-submission.pdf", response.headers["Content-Disposition"])
        self.assertNotIn("飞鹰队", response.headers["Content-Disposition"])
        response.close()

    def test_ac06_publish_snapshot_student_privacy_and_excel(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE peer_reviews SET score=80 WHERE project_id=1 AND target_team_id=1")
            db.execute("UPDATE process_scores SET score=80 WHERE project_id=1 AND team_id=1")
            db.execute("UPDATE final_scores SET score=80 WHERE project_id=1 AND team_id=1")
            db.commit()
        self.login("t1")
        response = self.post(
            "/api/individual-adjustments",
            json={"project_id": 1, "user_id": "s1", "coefficient": 0.8, "manual_deduction": 0, "reason": "AC-06 验收"},
        )
        self.assertEqual(response.status_code, 200)
        published = self.post("/api/projects/1/publish-grades")
        self.assertEqual(published.status_code, 200)
        xlsx = self.client.get("/api/projects/1/grades.xlsx")
        self.assertEqual(xlsx.status_code, 200)
        self.assertEqual(xlsx.mimetype, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        workbook = load_workbook(io.BytesIO(xlsx.data), data_only=True)
        self.assertEqual(workbook.sheetnames, ["团队汇总", "个人明细", "发布信息"])
        personal_rows = list(workbook["个人明细"].iter_rows(values_only=True))
        s1_row = next(values for values in personal_rows[1:] if values[1] == "s1")
        self.assertEqual(s1_row[-1], 64)
        pdf = self.client.get("/api/projects/1/grades.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

        self.login("s1")
        data = self.client.get("/api/bootstrap").get_json()
        grade = data["projects"][0]["gradebook"][0]
        self.assertEqual(grade["individual_score"], 64)
        self.assertEqual(set(grade), {"team_id", "team_name", "peer_score", "individual_score"})
        blocked = self.post("/api/reviews", json={"project_id": 1, "assignment_id": data["review_targets"][0]["assignment_id"], "score": 90, "comment": "发布后修改"})
        self.assertEqual(blocked.status_code, 403)

    def test_assistant_cannot_write_teacher_score_or_see_final_score(self):
        self.login("ta1")
        data = self.client.get("/api/bootstrap").get_json()
        self.assertTrue(data["projects"][0]["gradebook"])
        self.assertNotIn("final_score", data["projects"][0]["gradebook"][0])
        self.assertNotIn("total", data["projects"][0]["gradebook"][0])
        response = self.post("/api/scores/final", json={"project_id": 1, "team_id": 1, "score": 99})
        self.assertEqual(response.status_code, 403)

    def test_unpublish_preserves_snapshot_history(self):
        self.login("t1")
        self.assertEqual(self.post("/api/projects/1/publish-grades").status_code, 200)
        response = self.post("/api/projects/1/unpublish-grades", json={"reason": "复核后重发"})
        self.assertEqual(response.status_code, 200)
        with platform_app.app.app_context():
            publication = platform_app.row("SELECT active,withdrawal_reason FROM grade_publications WHERE project_id=1 ORDER BY version DESC LIMIT 1")
            snapshot_count = platform_app.row("SELECT COUNT(*) AS n FROM team_grade_snapshots WHERE project_id=1")["n"]
        self.assertEqual(publication["active"], 0)
        self.assertEqual(publication["withdrawal_reason"], "复核后重发")
        self.assertEqual(snapshot_count, 4)

    def test_score_team_must_belong_to_project(self):
        self.login("t1")
        response = self.post("/api/scores/final", json={"project_id": 1, "team_id": 999, "score": 90, "comment": "测试"})
        self.assertEqual(response.status_code, 400)

    def test_notification_can_be_marked_read(self):
        self.login("s1")
        notification_id = self.client.get("/api/bootstrap").get_json()["notifications"][0]["id"]
        self.assertEqual(self.post(f"/api/notifications/{notification_id}/read").status_code, 200)

    def test_v4_login_lockout_after_five_failures(self):
        for _ in range(5):
            self.assertEqual(self.login("s1", "wrong-password").status_code, 401)
        locked = self.login("s1", "123456")
        self.assertEqual(locked.status_code, 423)
        self.assertIn("锁定", locked.get_json()["message"])

    def test_v4_course_project_draft_and_publish(self):
        self.login("t1")
        course = self.post("/api/courses", json={"name": "软件测试", "term": "2027 春"})
        self.assertEqual(course.status_code, 200)
        course_id = course.get_json()["course_id"]
        draft = self.post(
            "/api/projects",
            json={
                "course_id": course_id,
                "title": "测试实践项目",
                "description": "完成测试闭环",
                "team_deadline": "2027-03-10 23:59:00",
                "overall_deadline": "2027-06-10 23:59:00",
                "review_deadline": "2027-06-01 23:59:00",
                "save_as_draft": True,
                "iterations": [{"name": "迭代 1", "deadline": "2027-05-01 23:59:00", "requirements": "提交测试报告"}],
            },
        )
        self.assertEqual(draft.status_code, 200)
        project_id = draft.get_json()["project_id"]
        with platform_app.app.app_context():
            self.assertEqual(platform_app.row("SELECT status FROM projects WHERE id=?", (project_id,))["status"], "draft")
        self.assertEqual(self.post(f"/api/projects/{project_id}/publish").status_code, 200)

    def test_v4_join_request_requires_leader_approval(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM team_members WHERE team_id=1 AND user_id='s9'")
            db.execute("UPDATE projects SET team_deadline='2026-12-01 23:59:00' WHERE id=1")
            db.commit()
        self.login("s9")
        requested = self.post("/api/teams/2/join")
        self.assertEqual(requested.status_code, 200)
        with platform_app.app.app_context():
            join_request = platform_app.row("SELECT id,status FROM team_join_requests WHERE team_id=2 AND user_id='s9'")
        self.assertEqual(join_request["status"], "pending")
        self.login("s3")
        approved = self.post(f"/api/team-join-requests/{join_request['id']}/decision", json={"decision": "approved"})
        self.assertEqual(approved.status_code, 200)
        with platform_app.app.app_context():
            self.assertIsNotNone(platform_app.row("SELECT 1 FROM team_members WHERE team_id=2 AND user_id='s9'"))

    def test_v4_member_task_allows_designated_member_submission(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE projects SET review_open=0 WHERE id=1")
            db.commit()
        self.login("s1")
        created = self.post(
            "/api/member-tasks",
            json={
                "project_id": 1,
                "iteration_id": 2,
                "assignee_id": "s2",
                "title": "提交设计成果",
                "description": "整理设计文档并提交",
                "due_at": "2026-12-01 23:59:00",
            },
        )
        self.assertEqual(created.status_code, 200)
        self.login("s2")
        uploaded = self.post(
            "/api/submissions/2",
            data={"file": (io.BytesIO(b"%PDF-1.7\n%%EOF"), "design.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(uploaded.status_code, 200)

    def test_v4_process_return_and_iteration_score(self):
        self.login("ta1")
        returned = self.post(
            "/api/process-checks",
            json={"project_id": 1, "team_id": 1, "iteration_id": 1, "action": "returned", "comment": "补充验收依据"},
        )
        self.assertEqual(returned.status_code, 200)
        with platform_app.app.app_context():
            self.assertEqual(platform_app.row("SELECT status FROM submissions WHERE team_id=1 AND iteration_id=1")["status"], "returned")
        received = self.post(
            "/api/process-checks",
            json={"project_id": 1, "team_id": 1, "iteration_id": 1, "action": "received", "score": 88, "comment": "修改后查收"},
        )
        self.assertEqual(received.status_code, 200)
        with platform_app.app.app_context():
            self.assertEqual(platform_app.row("SELECT score FROM process_scores WHERE project_id=1 AND team_id=1")["score"], 88)

    def test_v4_multidimensional_review_draft_and_alert(self):
        self.login("s1")
        assignment = self.client.get("/api/bootstrap").get_json()["review_targets"][0]["assignment_id"]
        draft = self.post(
            "/api/reviews",
            json={"project_id": 1, "assignment_id": assignment, "completeness_score": 0, "innovation_score": 0, "documentation_score": 0, "comment": "", "status": "draft"},
        )
        self.assertEqual(draft.status_code, 200)
        submitted = self.post(
            "/api/reviews",
            json={"project_id": 1, "assignment_id": assignment, "completeness_score": 0, "innovation_score": 0, "documentation_score": 0, "comment": "需要全面改进", "status": "submitted"},
        )
        self.assertEqual(submitted.status_code, 200)
        with platform_app.app.app_context():
            review = platform_app.row("SELECT completeness_score,innovation_score,documentation_score,status FROM peer_reviews WHERE reviewer_id='s1' AND project_id=1 AND completeness_score IS NOT NULL ORDER BY id LIMIT 1")
            self.assertEqual(review["status"], "submitted")
            self.assertEqual(review["completeness_score"], 0)
            self.assertIsNotNone(platform_app.row("SELECT 1 FROM review_alerts WHERE project_id=1 AND status='open'"))

    def test_v4_grade_appeal_admin_resolution(self):
        self.login("t1")
        self.assertEqual(self.post("/api/projects/1/publish-grades").status_code, 200)
        self.login("s1")
        appeal = self.post("/api/grade-appeals", json={"project_id": 1, "reason": "过程检查记录需要复核"})
        self.assertEqual(appeal.status_code, 200)
        with platform_app.app.app_context():
            appeal_id = platform_app.row("SELECT id FROM grade_appeals WHERE project_id=1 AND user_id='s1'")["id"]
        self.login("a1")
        resolved = self.post(f"/api/grade-appeals/{appeal_id}/resolve", json={"decision": "approved", "result": "已核查，教师将撤回后重发"})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(self.post("/api/projects/1/unpublish-grades", json={"reason": "执行复核结论"}).status_code, 200)
        verification = self.client.get("/api/audit/verify")
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.get_json()["valid"])
        backup = self.post("/api/admin/backup")
        self.assertEqual(backup.status_code, 200)
        self.assertTrue(Path(backup.get_json()["file"]).exists())


if __name__ == "__main__":
    unittest.main()

