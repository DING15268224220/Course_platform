import io
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_grade_math(self):
        with platform_app.app.app_context():
            grades = platform_app.gradebook(1)
        code_team = next(item for item in grades if item["team_name"] == "代码之神")
        self.assertEqual(code_team["total"], 89.75)

    def test_small_team_cannot_submit(self):
        with platform_app.app.app_context():
            db = platform_app.get_db()
            db.execute("DELETE FROM team_members WHERE team_id=1 AND user_id='s9'")
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
            db.commit()
        self.login("s9")
        response = self.client.get("/api/submissions/2/download")
        self.assertEqual(response.status_code, 403)
        response.close()

    def test_review_requires_assignment(self):
        self.login("s9")
        response = self.post("/api/reviews", json={"project_id": 1, "target_team_id": 2, "score": 88, "comment": "结构清晰"})
        self.assertEqual(response.status_code, 403)

    def test_score_team_must_belong_to_project(self):
        self.login("t1")
        response = self.post("/api/scores/final", json={"project_id": 1, "team_id": 999, "score": 90, "comment": "测试"})
        self.assertEqual(response.status_code, 400)

    def test_notification_can_be_marked_read(self):
        self.login("s1")
        notification_id = self.client.get("/api/bootstrap").get_json()["notifications"][0]["id"]
        self.assertEqual(self.post(f"/api/notifications/{notification_id}/read").status_code, 200)


if __name__ == "__main__":
    unittest.main()

