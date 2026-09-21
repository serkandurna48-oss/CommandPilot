"""
Tests for app/models/project.py's website_url validation — added for the
"Product Websites" card grid (ProductWebsites.tsx), which turns this field
into a clickable external link. Catching an obviously malformed URL here
beats surfacing a broken link in the UI.

Run:
    python -m pytest backend/tests/test_project_model.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import ValidationError  # noqa: E402

from app.models.project import ProjectCreate, ProjectUpdate  # noqa: E402


class ProjectWebsiteUrlValidationTests(unittest.TestCase):
    def test_accepts_https_url(self):
        p = ProjectCreate(name="CampPilot", website_url="https://camppilot.example.com")
        self.assertEqual(p.website_url, "https://camppilot.example.com")

    def test_accepts_http_url(self):
        p = ProjectCreate(name="CampPilot", website_url="http://camppilot.example.com")
        self.assertEqual(p.website_url, "http://camppilot.example.com")

    def test_none_is_allowed(self):
        p = ProjectCreate(name="CampPilot")
        self.assertIsNone(p.website_url)

    def test_empty_string_normalizes_to_none(self):
        p = ProjectCreate(name="CampPilot", website_url="")
        self.assertIsNone(p.website_url)

    def test_rejects_url_without_scheme(self):
        with self.assertRaises(ValidationError):
            ProjectCreate(name="CampPilot", website_url="camppilot.example.com")

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ValidationError):
            ProjectCreate(name="CampPilot", website_url="javascript:alert(1)")

    def test_update_model_applies_same_validation(self):
        with self.assertRaises(ValidationError):
            ProjectUpdate(website_url="not-a-url")
        u = ProjectUpdate(website_url="https://camppilot.example.com")
        self.assertEqual(u.website_url, "https://camppilot.example.com")


if __name__ == "__main__":
    unittest.main()
