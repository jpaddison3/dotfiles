import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render", ROOT / "claude-skills/meeting-options/render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class ShowTest(unittest.TestCase):
    def test_bb_thread_opens_nothing(self):
        with mock.patch.dict(os.environ, {"BB_THREAD_ID": "thr_x"}), mock.patch.object(render.subprocess, "run") as run:
            line = render.show("/x/opts.png")
        run.assert_not_called()
        self.assertTrue(line.startswith("not opened"), line)
        self.assertIn("inline", line)

    def test_outside_bb_opens_preview(self):
        env = {k: v for k, v in os.environ.items() if k != "BB_THREAD_ID"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(render.subprocess, "run") as run:
            line = render.show("/x/opts.png")
        run.assert_called_once_with(["open", "-a", "Preview", "/x/opts.png"], check=True)
        self.assertEqual(line, "opened in Preview: /x/opts.png")

    def test_empty_bb_thread_id_is_outside_bb(self):
        with mock.patch.dict(os.environ, {"BB_THREAD_ID": ""}), mock.patch.object(render.subprocess, "run") as run:
            line = render.show("/x/opts.png")
        run.assert_called_once()
        self.assertTrue(line.startswith("opened in Preview"), line)


if __name__ == "__main__":
    unittest.main()
