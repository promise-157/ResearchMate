import os
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Response


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.items import (
    confirm_item_template as confirm_template_api,
    extract_item_template as extract_template_api,
    get_item_template as get_template_api,
    list_items,
)
from services.materials import import_text_material
from services.template_registry import (
    TEMPLATE_SPECS,
    confirm_item_template,
    extract_item_template,
    get_item_template,
)
from storage.models import MaterialCreate, TemplateConfirmationRequest
from api.routes.items import create_item
from storage.workspace import _init_workspace_db


class JobTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "jobs.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.materials.get_active_connection", side_effect=self.connect),
            patch("services.materials._update_workspace_item_count"),
            patch("services.template_registry.get_active_connection", side_effect=self.connect),
        ]
        for active in self.patches:
            active.start()

    def tearDown(self):
        for active in reversed(self.patches):
            active.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_job(self, *, company="星河科技", status="待投递"):
        item, _ = import_text_material(
            item_type="job",
            content_text=(
                f"公司: {company}\n"
                "岗位: 后端工程师\n"
                "地区: 上海 / 混合办公\n"
                "薪资: 30k-45k·14薪\n"
                "技能: Python, FastAPI, SQLite\n"
                "经验年限: 3-5年\n"
                f"投递状态: {status}"
            ),
        )
        return item

    def test_job_schema_is_extracted_on_import_and_audited(self):
        item = self.create_job()
        template = get_item_template(item["id"])
        self.assertEqual(template["template_key"], "job")
        self.assertEqual(template["schema_version"], 1)
        self.assertEqual(template["extracted"]["company"], "星河科技")
        self.assertEqual(template["extracted"]["role"], "后端工程师")
        self.assertEqual(template["extracted"]["experience"], "3-5年")

        conn = self.connect()
        run = conn.execute(
            "SELECT processor, run_kind, provider, status FROM extraction_runs"
        ).fetchone()
        conn.close()
        self.assertEqual(
            tuple(run), ("job_label_rules", "template_extract", "local", "succeeded")
        )

    def test_confirmation_wins_filtering_and_survives_reprocessing(self):
        item = self.create_job()
        confirmed = confirm_item_template(item["id"], {
            "company": "用户确认公司",
            "application_status": "已投递",
        })
        self.assertEqual(confirmed["effective"]["company"], "用户确认公司")

        rerun = extract_item_template(item["id"])
        self.assertEqual(rerun["extracted"]["company"], "星河科技")
        self.assertEqual(rerun["confirmed"]["company"], "用户确认公司")
        self.assertEqual(rerun["effective"]["company"], "用户确认公司")

        confirmed_match = list_items(
            q=None, item_type="job", status=None, debug_error=None,
            job_company="用户确认", job_role="后端", job_application_status="已投递",
            include_accepted_extractions=False, page=1, page_size=20,
        )
        extracted_hidden = list_items(
            q=None, item_type="job", status=None, debug_error=None,
            job_company="星河科技", job_role=None, job_application_status=None,
            include_accepted_extractions=False, page=1, page_size=20,
        )
        self.assertEqual(confirmed_match["total"], 1)
        self.assertEqual(extracted_hidden["total"], 0)

    def test_api_dispatch_validates_fields_and_persists(self):
        response = Response()
        created = create_item(MaterialCreate(
            content_text="Company: Northwind\nRole: Data Engineer\nStatus: interested",
            item_type="job",
        ), response)
        item_id = created["item"]["id"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(get_template_api(item_id)["extracted"]["company"], "Northwind")

        saved = confirm_template_api(
            item_id, TemplateConfirmationRequest({"role": "Senior Data Engineer"})
        )
        self.assertEqual(saved["effective"]["role"], "Senior Data Engineer")
        self.assertEqual(extract_template_api(item_id)["confirmed"]["role"], "Senior Data Engineer")

        with self.assertRaises(HTTPException) as caught:
            confirm_template_api(
                item_id, TemplateConfirmationRequest({"unexpected": "value"})
            )
        self.assertEqual(caught.exception.status_code, 400)

    def test_extractor_failure_is_recorded_and_reported(self):
        item = self.create_job()

        def fail(_text):
            raise ValueError("fixture parser failure")

        broken = replace(TEMPLATE_SPECS["job"], extract=fail)
        with patch.dict(TEMPLATE_SPECS, {"job": broken}):
            with self.assertRaises(HTTPException) as caught:
                extract_template_api(item["id"])
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("fixture parser failure", caught.exception.detail)

        conn = self.connect()
        run = conn.execute(
            "SELECT status, error_message FROM extraction_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        self.assertEqual(run["status"], "failed")
        self.assertIn("fixture parser failure", run["error_message"])


if __name__ == "__main__":
    unittest.main()
