"""FR-09.6 notification content: 2 templates x 2 channels (no database, no sending)."""
import contextlib
import io
import unittest

from scripts import check_templates


class NotificationTemplateTests(unittest.TestCase):
    def test_ready_templates_sms_and_email(self):
        check_templates.results.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            failed = check_templates.main()
        failures = [f"{name}: {detail}" for ok, name, detail in check_templates.results if not ok]
        self.assertEqual(failed, 0, "\n".join(failures))
        self.assertGreaterEqual(len(check_templates.results), 15)


if __name__ == "__main__":
    unittest.main()
