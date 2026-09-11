from __future__ import annotations

import unittest

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.app_help import APP_HELP, help_for


class AppHelpTests(unittest.TestCase):
    def test_every_published_application_has_a_complete_guide(self) -> None:
        published_keys = {app.key for app in APP_REGISTRY}
        self.assertEqual(set(APP_HELP), published_keys)
        for app in APP_REGISTRY:
            guide = help_for(app)
            self.assertTrue(guide.purpose)
            self.assertTrue(guide.benefit)
            self.assertTrue(guide.input_hint)
            self.assertTrue(guide.output_hint)
            self.assertTrue(guide.tip)
            self.assertGreaterEqual(len(guide.steps), 3)


if __name__ == "__main__":
    unittest.main()
