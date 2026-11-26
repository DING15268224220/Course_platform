"""Additional API acceptance tests for routes not covered by backend/tests/test_app.py."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
import app as platform_app  # noqa: E402


class FullApiCoverageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name) / "data"
        platform_app.DATA_DIR = data_dir
        platform_app.UPLOAD_DIR = data_dir / "uploads"
        platform_app.DB_PATH = data_dir / "platform.db"
        platform_app.app.config.update(TESTING=True, SECRET_KEY="full-api-test-secret")
        with platform_app.app.app_context():
            platform_app.init_db()
            db = platform_app.get_db()
            db.execute("UPDATE projects SET team_deadline='2099-01-01 00:00:00', overall_deadline='2099-12-31 23:59:59', review_deadline='2099-12-01 23:59:59'")
            db.execute("UPDATE iterations SET deadline='2099-11-30 23:59:59'")
            db.commit()
        self.client = platform_app.app.test_client()
        self.csrf = ""

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, user_id: str, password: str = "123456"):
        response = self.client.post("/api/login", json={"user_id": user_id, "password": password})
        if response.status_code == 200:
            self.csrf = response.get_json()["csrf_token"]
        return response

    def request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-CSRF-Token"] = self.csrf
        return self.client.open(path, method=method, headers=headers, **kwargs)

    def test_public_endpoints_session_notifications_and_logout(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        users = self.client.get("/api/demo-users")
        self.assertEqual(users.status_code, 200)
        self.assertGreaterEqual(len(users.get_json()["users"]), 4)
        self.assertFalse(self.client.get("/api/session").get_json()["authenticated"])
        self.assertEqual(self.login("s1").status_code, 200)
        self.assertTrue(self.client.get("/api/session").get_json()["authenticated"])
        self.assertEqual(self.request("POST", "/api/notifications/read-all").status_code, 200)
        self.assertEqual(self.request("POST", "/api/logout").status_code, 200)
        self.assertFalse(self.client.get("/api/session").get_json()["authenticated"])

    def test_project_update_and_add_iteration(self):
        self.login("t1")
        updated = self.request("PATCH", "/api/projects/1", json={"title": "软件工程综合实践（验收）", "peer_weight": 30, "process_weight": 30, "final_weight": 40})
        self.assertEqual(updated.status_code, 200)
        added = self.request("POST", "/api/projects/1/iterations", json={"name": "验收迭代", "requirements": "提交最终验收材料", "deadline": "2099-10-01 23:59:59"})
        self.assertEqual(added.status_code, 200)
        with platform_app.app.app_context():
            self.assertIsNotNone(platform_app.row("SELECT 1 FROM iterations WHERE project_id=1 AND name='验收迭代'"))

    def test_create_team_leave_and_teacher_member_adjustment(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM team_members WHERE user_id='s9'")
            db.commit()
        self.login("s9")
        created = self.request("POST", "/api/teams", json={"project_id": 1, "name": "自动化验收团队"})
        self.assertEqual(created.status_code, 200)
        with platform_app.app.app_context():
            team_id = platform_app.row("SELECT id FROM teams WHERE name='自动化验收团队'")["id"]
        self.assertEqual(self.request("POST", f"/api/teams/{team_id}/leave").status_code, 200)
        self.login("t1")
        added = self.request("POST", "/api/teams/2/members/adjust", json={"action": "add", "user_id": "s9", "reason": "验收例外加入"})
        self.assertEqual(added.status_code, 200)
        removed = self.request("POST", "/api/teams/2/members/adjust", json={"action": "remove", "user_id": "s9", "reason": "验收例外移除"})
        self.assertEqual(removed.status_code, 200)

    def test_member_task_creation_and_status_update(self):
        self.login("s1")
        created = self.request("POST", "/api/member-tasks", json={"project_id": 1, "iteration_id": 1, "assignee_id": "s2", "title": "验收测试任务", "description": "执行完整功能验收", "due_at": "2099-09-01 23:59:59"})
        self.assertEqual(created.status_code, 200)
        with platform_app.app.app_context():
            task_id = platform_app.row("SELECT id FROM member_tasks WHERE title='验收测试任务'")["id"]
        self.login("s2")
        response = self.request("PATCH", f"/api/member-tasks/{task_id}", json={"status": "done"})
        self.assertEqual(response.status_code, 200)

    def test_submission_upload_download_versions_and_withdraw(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE projects SET review_open=0 WHERE id=1")
            db.commit()
        self.login("s1")
        uploaded = self.request("POST", "/api/submissions/1", data={"file": (io.BytesIO(b"%PDF-1.7\nacceptance\n%%EOF"), "acceptance.pdf")}, content_type="multipart/form-data")
        self.assertEqual(uploaded.status_code, 200)
        with platform_app.app.app_context():
            submission_id = platform_app.row("SELECT id FROM submissions WHERE team_id=1 AND iteration_id=1")["id"]
        download = self.client.get(f"/api/submissions/{submission_id}/download")
        self.assertEqual(download.status_code, 200)
        download.close()
        versions = self.client.get(f"/api/submissions/{submission_id}/versions")
        self.assertEqual(versions.status_code, 200)
        self.assertTrue(versions.get_json()["versions"])
        self.assertEqual(self.request("POST", f"/api/submissions/{submission_id}/withdraw").status_code, 200)

    def test_reminders_review_toggle_alert_resolution_and_scores(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE projects SET review_open=1 WHERE id=1")
            db.execute("INSERT INTO review_alerts(project_id,target_team_id,alert_type,detail,status,created_at) VALUES(1,1,'spread','验收预警','open',?)", (platform_app.now_iso(),))
            alert_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()
        self.login("t1")
        self.assertEqual(self.request("POST", "/api/projects/1/toggle-review").status_code, 200)
        self.assertEqual(self.request("POST", "/api/projects/1/toggle-review").status_code, 200)
        self.assertEqual(self.request("POST", "/api/scores/final", json={"project_id": 1, "team_id": 1, "score": 91, "comment": "验收终评"}).status_code, 200)
        self.login("ta1")
        reminder = self.request("POST", "/api/projects/1/remind-missing", json={"iteration_id": 2})
        self.assertEqual(reminder.status_code, 200)
        self.assertIn("teams", reminder.get_json())
        self.assertEqual(self.request("POST", "/api/scores/process", json={"project_id": 1, "team_id": 1, "score": 89, "comment": "验收过程分"}).status_code, 200)
        self.assertEqual(self.request("POST", f"/api/review-alerts/{alert_id}/resolve", json={"resolution": "人工复核无异常"}).status_code, 200)

    def test_csv_export_after_grade_publication(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("UPDATE peer_reviews SET score=80 WHERE project_id=1")
            db.execute("UPDATE process_scores SET score=80 WHERE project_id=1")
            db.execute("UPDATE final_scores SET score=80 WHERE project_id=1")
            db.execute("UPDATE review_alerts SET status='resolved' WHERE project_id=1")
            db.commit()
        self.login("t1")
        published = self.request("POST", "/api/projects/1/publish-grades")
        self.assertEqual(published.status_code, 200)
        exported = self.client.get("/api/projects/1/grades.csv")
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(exported.data.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
