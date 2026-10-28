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
    def test_bb_thread_opens_nothing_and_names_image_path(self):
        with tempfile.TemporaryDirectory() as storage:
            png = os.path.join(storage, "specs", "opts.png")
            env = {"BB_THREAD_ID": "thr_x", "BB_THREAD_STORAGE": storage}
            with mock.patch.dict(os.environ, env), mock.patch.object(render.subprocess, "run") as run:
                line = render.show(png)
        run.assert_not_called()
        self.assertTrue(line.startswith("not opened"), line)
        self.assertIn('Image("$BB_THREAD_STORAGE/specs/opts.png")', line)

    def test_bb_thread_png_outside_storage_says_so(self):
        with tempfile.TemporaryDirectory() as storage:
            env = {"BB_THREAD_ID": "thr_x", "BB_THREAD_STORAGE": storage}
            with mock.patch.dict(os.environ, env), mock.patch.object(render.subprocess, "run") as run:
                line = render.show("/elsewhere/opts.png")
        run.assert_not_called()
        self.assertTrue(line.startswith("not opened"), line)
        self.assertIn("outside $BB_THREAD_STORAGE", line)
        self.assertNotIn("Image(", line)

    def test_outside_bb_opens_preview_even_in_orca(self):
        env = {k: v for k, v in os.environ.items() if k != "BB_THREAD_ID"}
        env["ORCA_WORKTREE_ID"] = "wt_x"
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(render.subprocess, "run") as run:
            line = render.show("/x/opts.png")
        run.assert_called_once_with(["open", "-a", "Preview", "/x/opts.png"], check=True)
        self.assertEqual(line, "opened in Preview: /x/opts.png")

    def test_empty_bb_thread_id_is_outside_bb(self):
        with mock.patch.dict(os.environ, {"BB_THREAD_ID": ""}), mock.patch.object(render.subprocess, "run") as run:
            line = render.show("/x/opts.png")
        run.assert_called_once()
        self.assertTrue(line.startswith("opened in Preview"), line)


class MainTest(unittest.TestCase):
    def test_prints_png_path_then_location(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "opts.json"
            spec.write_text("{}")
            argv = ["render.py", str(spec), "--open"]
            with mock.patch.object(render.sys, "argv", argv), \
                    mock.patch.object(render, "build", return_value=("", 1, 1)), \
                    mock.patch.object(render, "render"), \
                    mock.patch.object(render, "show", return_value="LOCATION") as show, \
                    mock.patch("builtins.print") as out:
                render.main()
        png = str(spec.with_suffix(".png"))
        show.assert_called_once_with(png)
        self.assertEqual([c.args for c in out.call_args_list], [(png,), ("LOCATION",)])

    def test_focus_flag_is_gone(self):
        with mock.patch.object(render.sys, "argv", ["render.py", "x.json", "--focus"]), \
                mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            render.main()


if __name__ == "__main__":
    unittest.main()
