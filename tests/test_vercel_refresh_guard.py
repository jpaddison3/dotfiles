import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHIM_SRC = ROOT / "codex-shim" / "vercel-refresh-guard"

# Stands in for the real CLI, so nothing here touches the network or a real login.
FAKE_VERCEL = """#!/bin/sh
echo "REAL-VERCEL ARGS=$*"
echo "REAL-VERCEL-STDERR" >&2
cat
exit 7
"""

ACCESS_TOKEN = "access-token-do-not-print"
REFRESH_TOKEN = "refresh-token-do-not-print"

# Callers that match on these read them as the login being gone, so a block must not
# say them.
CLI_LOGIN_MESSAGES = (
    "No existing credentials found",
    "Starting login flow",
    "Waiting for authentication",
)


def auth(expires_in=-3600, **overrides):
    data = {
        "// Note": "This is your Vercel credentials file. DO NOT SHARE!",
        "token": ACCESS_TOKEN,
        "refreshToken": REFRESH_TOKEN,
        "expiresAt": int(time.time()) + expires_in,
    }
    data.update(overrides)
    return json.dumps(data)


class VercelRefreshGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.config = self.home / "Library" / "Application Support" / "com.vercel.cli"
        self.config.mkdir(parents=True)
        self.shim_dir = self.tmp / "shim"
        self.shim_dir.mkdir()
        (self.shim_dir / "vercel").symlink_to(SHIM_SRC)
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        fake = self.bin_dir / "vercel"
        fake.write_text(FAKE_VERCEL)
        fake.chmod(0o755)
        # node alone, not its folder: the real vercel lives next to it.
        self.node_dir = self.tmp / "node-only"
        self.node_dir.mkdir()
        (self.node_dir / "node").symlink_to(shutil.which("node"))

    # -- helpers -----------------------------------------------------------
    def write_auth(self, text, folder=None):
        (folder or self.config).mkdir(parents=True, exist_ok=True)
        (folder or self.config).joinpath("auth.json").write_text(text)

    def read_only(self, folder=None):
        """Make a folder unwritable, the way a sandbox makes it look to the guard."""
        folder = folder or self.config
        folder.chmod(0o555)
        self.addCleanup(folder.chmod, 0o755)

    def run_guard(self, *args, env=None, path=None, stdin="", prefix=(), name="vercel"):
        full_env = {
            "HOME": str(self.home),
            "PATH": path or os.pathsep.join(
                [str(self.shim_dir), str(self.bin_dir), str(self.node_dir), "/usr/bin", "/bin"]
            ),
            **(env or {}),
        }
        return subprocess.run(
            [*prefix, str(self.shim_dir / name), *args],
            env=full_env, cwd=self.home, input=stdin,
            capture_output=True, text=True, timeout=30,
        )

    def assert_blocked(self, result, folder=None):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("REAL-VERCEL", result.stdout + result.stderr)
        self.assertIn("needs refreshing", result.stderr)
        self.assertIn("Rerun the same command outside the sandbox", result.stderr)
        self.assertIn("permissions classifier", result.stderr)
        self.assertIn("Waiting doesn't help", result.stderr)
        self.assertIn("within 15 minutes", result.stderr)
        self.assertIn(str(folder or self.config), result.stderr)
        self.assertIn("The write failed with:", result.stderr)
        self.assert_no_tokens(result)

    def assert_passed_through(self, result, args="whoami"):
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn(f"REAL-VERCEL ARGS={args}", result.stdout)
        self.assertEqual(result.stderr, "REAL-VERCEL-STDERR\n")
        self.assert_no_tokens(result)

    def assert_no_tokens(self, result):
        output = result.stdout + result.stderr
        self.assertNotIn(ACCESS_TOKEN, output)
        self.assertNotIn(REFRESH_TOKEN, output)

    # -- sandboxed, expired ------------------------------------------------
    def test_blocks_and_leaves_auth_json_byte_identical(self):
        text = auth()
        self.write_auth(text)
        self.read_only()
        before = (self.config / "auth.json").read_bytes()
        result = self.run_guard("whoami")
        self.assert_blocked(result)
        self.assertEqual((self.config / "auth.json").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.config.iterdir()), ["auth.json"])

    def test_blocks_whatever_the_subcommand(self):
        self.write_auth(auth())
        self.read_only()
        for args in (("deploy", "--prod", "--yes"), ("env", "ls"), ()):
            self.assert_blocked(self.run_guard(*args))

    def test_block_message_avoids_the_clis_login_wording(self):
        self.write_auth(auth())
        self.read_only()
        result = self.run_guard("whoami")
        for message in CLI_LOGIN_MESSAGES:
            self.assertNotIn(message, result.stderr)

    def test_token_inside_the_margin_counts_as_expired(self):
        self.write_auth(auth(expires_in=850))
        self.read_only()
        self.assert_blocked(self.run_guard("whoami"))

    def test_token_just_outside_the_margin_passes_through(self):
        self.write_auth(auth(expires_in=950))
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami"))

    def test_empty_vercel_token_is_no_token(self):
        self.write_auth(auth())
        self.read_only()
        self.assert_blocked(self.run_guard("whoami", env={"VERCEL_TOKEN": ""}))

    def test_token_flag_after_double_dash_is_not_the_clis(self):
        self.write_auth(auth())
        self.read_only()
        self.assert_blocked(self.run_guard("dev", "--", "--token", "abc"))
        self.assert_blocked(self.run_guard("dev", "--", "-t", "abc"))

    def test_blocks_under_a_real_seatbelt_sandbox(self):
        # A folder with writable permissions that the sandbox denies: the case
        # `test -w` gets wrong. Can't nest inside another sandbox, so skip there.
        profile = f'(version 1)(allow default)(deny file-write* (subpath "{self.config}"))'
        prefix = ("/usr/bin/sandbox-exec", "-p", profile)
        try:
            subprocess.run([*prefix, "/usr/bin/true"], check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("sandbox-exec isn't available here")
        self.write_auth(auth())
        before = (self.config / "auth.json").read_bytes()
        self.assert_blocked(self.run_guard("whoami", prefix=prefix))
        self.assertEqual((self.config / "auth.json").read_bytes(), before)

    # -- sandboxed, nothing to refresh -------------------------------------
    def test_valid_token_passes_args_stdio_and_exit_code_through(self):
        self.write_auth(auth(expires_in=3600))
        self.read_only()
        result = self.run_guard("deploy", "a b", "--prod", stdin="from stdin\n")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, "REAL-VERCEL ARGS=deploy a b --prod\nfrom stdin\n")
        self.assertEqual(result.stderr, "REAL-VERCEL-STDERR\n")

    # -- unsandboxed -------------------------------------------------------
    def test_writable_folder_passes_through_and_leaves_no_probe(self):
        self.write_auth(auth())
        self.assert_passed_through(self.run_guard("whoami"))
        self.assertEqual(sorted(p.name for p in self.config.iterdir()), ["auth.json"])

    # -- explicit tokens ---------------------------------------------------
    def test_vercel_token_passes_through(self):
        self.write_auth(auth())
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami", env={"VERCEL_TOKEN": "x"}))

    def test_token_flags_pass_through(self):
        self.write_auth(auth())
        self.read_only()
        for args in (
            ("whoami", "--token", "x"),
            ("--token", "x", "whoami"),
            ("whoami", "--token=x"),
            ("whoami", "-t", "x"),
            ("whoami", "-dt", "x"),
        ):
            self.assert_passed_through(self.run_guard(*args), args=" ".join(args))

    # -- anything it doesn't understand ------------------------------------
    def test_no_auth_json_passes_through(self):
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami"))

    def test_no_config_folder_passes_through(self):
        self.config.rmdir()
        self.assert_passed_through(self.run_guard("whoami"))

    def test_unusual_auth_json_passes_through(self):
        no_expiry = json.loads(auth())
        del no_expiry["expiresAt"]
        no_refresh = json.loads(auth())
        del no_refresh["refreshToken"]
        no_token = json.loads(auth())
        del no_token["token"]
        for text in (
            f'{{"token": "{ACCESS_TOKEN}", not json',
            "[]",
            "null",
            "",
            json.dumps(no_expiry),
            json.dumps(no_refresh),
            json.dumps(no_token),
            auth(token=""),
            auth(token=123),
            auth(expiresAt="soon"),
            auth(refreshToken=""),
        ):
            with self.subTest(text=text):
                self.config.chmod(0o755)
                self.write_auth(text)
                self.read_only()
                self.assert_passed_through(self.run_guard("whoami"))

    def test_unreadable_auth_json_passes_through(self):
        self.write_auth(auth())
        path = self.config / "auth.json"
        path.chmod(0o000)
        self.addCleanup(path.chmod, 0o600)
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami"))

    def test_keyring_storage_passes_through_despite_a_stale_auth_json(self):
        self.write_auth(auth())
        (self.config / "config.json").write_text('{"credStorage": "keyring"}')
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami"))

    def test_keyring_storage_from_the_environment_passes_through(self):
        self.write_auth(auth())
        self.read_only()
        result = self.run_guard("whoami", env={"VERCEL_TOKEN_STORAGE": "keyring"})
        self.assert_passed_through(result)

    def test_auto_storage_passes_through(self):
        self.write_auth(auth())
        (self.config / "config.json").write_text('{"credStorage": "auto"}')
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami"))
        result = self.run_guard("whoami", env={"VERCEL_TOKEN_STORAGE": "auto"})
        self.assert_passed_through(result)

    def test_unknown_storage_values_pass_through(self):
        self.write_auth(auth())
        self.read_only()
        result = self.run_guard("whoami", env={"VERCEL_TOKEN_STORAGE": "future-store"})
        self.assert_passed_through(result)
        for text in ('{"credStorage": "future-store"}', "{not json"):
            with self.subTest(text=text):
                self.config.chmod(0o755)
                (self.config / "config.json").write_text(text)
                self.read_only()
                self.assert_passed_through(self.run_guard("whoami"))

    def test_storage_set_to_file_in_the_environment_beats_config_json(self):
        self.write_auth(auth())
        (self.config / "config.json").write_text('{"credStorage": "keyring"}')
        self.read_only()
        self.assert_blocked(self.run_guard("whoami", env={"VERCEL_TOKEN_STORAGE": "file"}))

    def test_storage_set_to_file_in_config_json_blocks(self):
        self.write_auth(auth())
        (self.config / "config.json").write_text('{"credStorage": "file"}')
        self.read_only()
        self.assert_blocked(self.run_guard("whoami"))

    def test_auth_json_with_a_byte_order_mark_is_read(self):
        self.write_auth("\ufeff" + auth())
        self.read_only()
        self.assert_blocked(self.run_guard("whoami"))

    def test_no_node_passes_through(self):
        self.write_auth(auth())
        self.read_only()
        path = os.pathsep.join([str(self.shim_dir), str(self.bin_dir), "/usr/bin", "/bin"])
        if shutil.which("node", path=path):
            self.skipTest("node is on the system PATH here")
        self.assert_passed_through(self.run_guard("whoami", path=path))

    def test_stray_node_output_passes_through(self):
        # A version-manager wrapper that prints and fails isn't an answer.
        self.write_auth(auth(expires_in=3600))
        self.read_only()
        wrapper = self.node_dir / "node"
        wrapper.unlink()
        wrapper.write_text("#!/bin/sh\necho 'wrapper says hello'\nexit 1\n")
        wrapper.chmod(0o755)
        self.assert_passed_through(self.run_guard("whoami"))

    def test_stray_node_output_with_exit_zero_passes_through(self):
        self.write_auth(auth(expires_in=3600))
        self.read_only()
        wrapper = self.node_dir / "node"
        wrapper.unlink()
        wrapper.write_text("#!/bin/sh\necho 'wrapper says hello'\n")
        wrapper.chmod(0o755)
        self.assert_passed_through(self.run_guard("whoami"))

    def test_node_options_preload_cant_change_the_answer(self):
        preload = self.tmp / "preload.js"
        preload.write_text('console.log("preload says hello");')
        env = {"NODE_OPTIONS": f"--require {preload}"}
        self.write_auth(auth(expires_in=3600))
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami", env=env))
        self.config.chmod(0o755)
        self.write_auth(auth())
        self.read_only()
        self.assert_blocked(self.run_guard("whoami", env=env))

    # -- which config folder -----------------------------------------------
    def test_global_config_flag_forms_choose_the_folder_to_check(self):
        other = self.tmp / "other-config"
        self.write_auth(auth(expires_in=3600))
        self.write_auth(auth(), folder=other)
        self.read_only(other)
        for args in (("-Q", str(other)), ("--global-config", str(other)),
                     (f"--global-config={other}",), ("-dQ", str(other))):
            self.assert_blocked(self.run_guard("whoami", *args), folder=other)

    def test_global_config_flag_overrides_an_expired_default(self):
        other = self.tmp / "other-config"
        self.write_auth(auth())
        self.read_only()
        self.write_auth(auth(expires_in=3600), folder=other)
        args = ("whoami", "-Q", str(other))
        self.assert_passed_through(self.run_guard(*args), args=" ".join(args))

    def test_global_config_relative_path_resolves_from_the_cwd(self):
        other = self.home / "relative-config"
        self.write_auth(auth(), folder=other)
        self.read_only(other)
        self.assert_blocked(self.run_guard("whoami", "-Q", "relative-config"), folder=other)

    def test_last_global_config_wins(self):
        first = self.tmp / "first"
        last = self.tmp / "last"
        self.write_auth(auth(expires_in=3600), folder=first)
        self.write_auth(auth(), folder=last)
        self.read_only(last)
        result = self.run_guard("-Q", str(first), "--global-config", str(last), "whoami")
        self.assert_blocked(result, folder=last)

    def test_xdg_data_home_is_used(self):
        folder = self.tmp / "xdg" / "com.vercel.cli"
        self.write_auth(auth(), folder=folder)
        self.read_only(folder)
        result = self.run_guard("whoami", env={"XDG_DATA_HOME": str(self.tmp / "xdg")})
        self.assert_blocked(result, folder=folder)

    def test_xdg_data_dirs_are_searched(self):
        self.config.rmdir()
        folder = self.tmp / "shared" / "com.vercel.cli"
        self.write_auth(auth(), folder=folder)
        self.read_only(folder)
        env = {"XDG_DATA_DIRS": f"{self.tmp / 'missing'}:{self.tmp / 'shared'}"}
        self.assert_blocked(self.run_guard("whoami", env=env), folder=folder)

    def test_legacy_xdg_now_folder_is_used_last(self):
        self.config.rmdir()
        folder = self.home / "Library" / "Application Support" / "now"
        self.write_auth(auth(), folder=folder)
        self.read_only(folder)
        self.assert_blocked(self.run_guard("whoami"), folder=folder)

    def test_legacy_now_folder_is_used_when_the_current_one_is_absent(self):
        self.config.rmdir()
        folder = self.home / ".now"
        self.write_auth(auth(), folder=folder)
        self.read_only(folder)
        self.assert_blocked(self.run_guard("whoami"), folder=folder)

    def test_current_folder_beats_the_legacy_one(self):
        self.write_auth(auth(expires_in=3600))
        legacy = self.home / ".now"
        self.write_auth(auth(), folder=legacy)
        self.read_only(legacy)
        self.assert_passed_through(self.run_guard("whoami"))

    # -- finding the real CLI ----------------------------------------------
    def test_installed_as_vc_it_guards_and_runs_the_real_cli(self):
        (self.shim_dir / "vc").symlink_to(SHIM_SRC)
        self.write_auth(auth())
        self.read_only()
        self.assert_blocked(self.run_guard("whoami", name="vc"))
        self.config.chmod(0o755)
        self.write_auth(auth(expires_in=3600))
        self.read_only()
        self.assert_passed_through(self.run_guard("whoami", name="vc"))

    def test_skips_its_own_directory_on_path(self):
        self.write_auth(auth(expires_in=3600))
        path = os.pathsep.join(
            [str(self.shim_dir), str(self.shim_dir), str(self.bin_dir), str(self.node_dir),
             "/usr/bin", "/bin"]
        )
        self.assert_passed_through(self.run_guard("whoami", path=path))

    def test_nothing_behind_the_shim_reports_command_not_found(self):
        (self.bin_dir / "vercel").unlink()
        result = self.run_guard("whoami")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stderr, "vercel: command not found\n")

    def test_nothing_behind_the_shim_names_the_command_as_typed(self):
        (self.bin_dir / "vercel").unlink()
        (self.shim_dir / "vc").symlink_to(SHIM_SRC)
        result = self.run_guard("whoami", name="vc")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stderr, "vc: command not found\n")


if __name__ == "__main__":
    unittest.main()
