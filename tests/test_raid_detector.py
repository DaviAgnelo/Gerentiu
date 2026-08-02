import datetime
import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src"
    / "gerentiu"
    / "cogs"
    / "raid_detector.py"
)
SPEC = importlib.util.spec_from_file_location("raid_detector", MODULE_PATH)
raid_detector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(raid_detector)


class FakeGuild:
    id = 321


class FakeMember:
    bot = False

    def __init__(self, member_id: int):
        self.id = member_id
        self.guild = FakeGuild()
        self.created_at = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=1)
        )


class FakeMessage:
    attachments = []
    content = "https://discord.gg/example suspicious raid message"

    def __init__(self, author: FakeMember):
        self.author = author
        self.guild = author.guild


class RaidDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = raid_detector.RaidDetector()

    def test_default_state_and_reset(self):
        self.assertEqual(self.detector.get_state(FakeGuild.id)["state"], "NORMAL")

        self.detector.register_join(FakeMember(1))
        self.detector.reset_guild(FakeGuild.id)

        self.assertEqual(self.detector.get_state(FakeGuild.id)["state"], "NORMAL")

    def test_join_and_message_signals_reach_under_raid(self):
        members = [FakeMember(member_id) for member_id in range(1, 6)]

        join_result = None
        for member in members:
            join_result = self.detector.register_join(member)

        self.assertIsNotNone(join_result)
        self.assertEqual(join_result["new_state"], "SUSPECTED")
        self.assertEqual(join_result["score"], 5)

        message_result = None
        for _ in range(3):
            message_result = self.detector.register_message(FakeMessage(members[0]))

        self.assertIsNotNone(message_result)
        self.assertEqual(message_result["new_state"], "UNDER_RAID")
        self.assertEqual(message_result["score"], 8)


if __name__ == "__main__":
    unittest.main()
