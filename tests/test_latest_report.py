import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from runner import SITRunner
from services.report_service import _list_artifacts


class LatestReportTests(unittest.TestCase):
    def test_report_writer_updates_stable_latest_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = SITRunner.__new__(SITRunner)
            runner.reports_dir = Path(directory)
            runner.reporting_config = {"html_report": {}}
            now = datetime(2026, 9, 16, 16, 0, 0)
            summary = {"total": 0, "passed": 0, "failed": 0, "pass_percent": 0.0}

            runner._write_html_report("20260916_160000", [], summary, now, now, artifact_tag="cas")

            report = runner.reports_dir / "report_cas_20260916_160000.html"
            latest = runner.reports_dir / "latest.html"
            self.assertTrue(report.exists())
            self.assertEqual(latest.read_bytes(), report.read_bytes())
            self.assertEqual(len(_list_artifacts(runner.reports_dir, "report_*.html", "HTML")), 1)


if __name__ == "__main__":
    unittest.main()
