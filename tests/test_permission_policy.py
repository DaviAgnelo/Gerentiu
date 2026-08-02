import pathlib
import sys
import unittest
from types import SimpleNamespace


SRC_PATH = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_PATH))

from gerentiu.permission_policy import (  # noqa: E402
    missing_antiraid_permissions,
    missing_antispam_permissions,
    required_antiraid_permissions,
    required_antispam_permissions,
)


def permissions(**grants):
    return SimpleNamespace(**grants)


class PermissionPolicyTests(unittest.TestCase):
    def test_warn_requires_only_manage_messages(self):
        self.assertEqual(
            required_antispam_permissions("warn"),
            (("manage_messages", "Manage Messages"),),
        )

    def test_ban_progression_requires_every_moderation_step(self):
        missing = missing_antispam_permissions(
            permissions(manage_messages=True),
            "ban",
        )
        self.assertEqual(
            missing,
            ["Moderate Members", "Kick Members", "Ban Members"],
        )

    def test_timeout_does_not_require_kick_or_ban(self):
        missing = missing_antispam_permissions(
            permissions(manage_messages=True, moderate_members=True),
            "timeout",
        )
        self.assertEqual(missing, [])

    def test_alert_only_antiraid_has_no_management_permission(self):
        self.assertEqual(required_antiraid_permissions("alert"), ())
        self.assertEqual(missing_antiraid_permissions(permissions(), "alert"), [])

    def test_lockdown_requires_manage_channels(self):
        self.assertEqual(
            missing_antiraid_permissions(permissions(), "lockdown"),
            ["Manage Channels"],
        )


if __name__ == "__main__":
    unittest.main()
