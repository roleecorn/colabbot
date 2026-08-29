import asyncio
import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cmds.gitRely.event_service import EventService, EventServiceError
from cmds.gitRely.christmas_service import ChristmasService, ChristmasServiceError
from cmds.gitRely.models import EventStatus, event_status
from cmds.gitRely.models import GiftAssignment
from cmds.gitRely.repositories import EventRepository
from cmds.gitRely.storage import SubmissionStorage
from cmds.gitRely.submission_service import SubmissionService, SubmissionServiceError
from cmds.gitRely.event_cog import EventCog


TZ = ZoneInfo("Asia/Taipei")


class FakeInteractionResponse:
    def __init__(self):
        self.done = False
        self.messages = []

    def is_done(self):
        return self.done

    async def defer(self, **_kwargs):
        self.done = True

    async def send_message(self, content, **kwargs):
        self.done = True
        self.messages.append((content, kwargs))


class FakeInteraction:
    def __init__(self, user_id, channel_id=42):
        self.user = type("User", (), {"id": user_id, "name": "tester"})()
        self.channel_id = channel_id
        self.response = FakeInteractionResponse()
        self.followups = []
        owner = self

        class Followup:
            async def send(self, content, **kwargs):
                owner.followups.append((content, kwargs))

        self.followup = Followup()
        self.channel = type("Channel", (), {})()


def make_event(service, key="event-a", event_type="submission"):
    event = asyncio.run(
        service.create_event(
            event_key=key,
            display_name=key,
            event_type=event_type,
            timezone="Asia/Taipei",
            registration_channel_id="42",
            registration_starts_at=datetime(2026, 1, 1, tzinfo=TZ),
            registration_ends_at=datetime(2026, 1, 2, tzinfo=TZ),
            submission_starts_at=datetime(2026, 1, 3, tzinfo=TZ),
            submission_ends_at=datetime(2026, 1, 4, tzinfo=TZ),
            topics=["one", "two"],
            matching_policy="rules_2026" if event_type == "christmas" else None,
        )
    )
    asyncio.run(service.activate_event(key))
    return event


class EventRefactorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repository = EventRepository(root / "data", root / "public")
        self.service = EventService(self.repository)

    def tearDown(self):
        self.temp.cleanup()

    def test_status_boundaries_are_derived(self):
        event = make_event(self.service)
        self.assertEqual(event_status(event.private, datetime(2025, 12, 31, 23, 59, tzinfo=TZ)), EventStatus.SCHEDULED)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 1, tzinfo=TZ)), EventStatus.REGISTRATION_OPEN)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 2, tzinfo=TZ)), EventStatus.WAITING_SUBMISSION)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 3, tzinfo=TZ)), EventStatus.SUBMISSION_OPEN)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 4, tzinfo=TZ)), EventStatus.CLOSED)

    def test_join_uses_random_private_key(self):
        make_event(self.service)
        self.service.clock = lambda: datetime(2026, 1, 1, 12, tzinfo=TZ)
        participant = asyncio.run(self.service.join("123", "name"))
        self.assertNotEqual(participant.participant_key, "123")
        self.assertNotIn("123", participant.participant_key)
        public = json.dumps(self.repository.load_public("event-a").to_dict())
        self.assertNotIn("123", public)

    def test_switching_active_event_does_not_reuse_participants(self):
        make_event(self.service, "one")
        make_event(self.service, "two")
        self.service.clock = lambda: datetime(2026, 1, 1, tzinfo=TZ)
        asyncio.run(self.service.activate_event("one"))
        asyncio.run(self.service.join("123"))
        asyncio.run(self.service.activate_event("two"))
        self.assertIsNone(asyncio.run(self.service.participant("123")))

    def test_path_traversal_archive_is_rejected(self):
        root = Path(self.temp.name)
        archive = root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("../escape.txt", "no")
        destination = root / "staged"
        with self.assertRaises(ValueError):
            SubmissionStorage().extract_archive(archive, destination)
        self.assertFalse(destination.exists())

    def test_failed_publish_restores_previous_submission(self):
        event = make_event(self.service, "upload")
        self.service.clock = lambda: datetime(2026, 1, 1, 12, tzinfo=TZ)
        participant = asyncio.run(self.service.join("123"))
        self.service.clock = lambda: datetime(2026, 1, 3, 12, tzinfo=TZ)
        root = Path(self.temp.name)
        archive_one = root / "one.zip"
        with zipfile.ZipFile(archive_one, "w") as output:
            output.writestr("old.png", b"old")
        archive_two = root / "two.zip"
        with zipfile.ZipFile(archive_two, "w") as output:
            output.writestr("new.png", b"new")

        class Publisher:
            def __init__(self):
                self.calls = 0

            async def publish(self, *_args):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("push failed")

        publisher = Publisher()
        submissions = SubmissionService(
            self.service,
            SubmissionStorage(root / "uploads"),
            publisher,
            pages_host="https://pages.example",
        )
        asyncio.run(
            submissions.upload_archive(
                "123", archive_one, topic="one", title="old", now=datetime(2026, 1, 3, tzinfo=TZ)
            )
        )
        with self.assertRaises(SubmissionServiceError):
            asyncio.run(
                submissions.upload_archive(
                    "123", archive_two, topic="one", title="new", now=datetime(2026, 1, 3, tzinfo=TZ)
                )
            )
        target = self.repository.public_dir("upload") / "pieces" / participant.participant_key
        self.assertEqual((target / event.public.topics[0].key / "old.png").read_bytes(), b"old")
        self.assertFalse((target / event.public.topics[0].key / "new.png").exists())

    def test_clear_is_rejected_after_submission_deadline(self):
        event = make_event(self.service, "clear")
        self.service.clock = lambda: datetime(2026, 1, 1, 12, tzinfo=TZ)
        participant = asyncio.run(self.service.join("123"))
        topic_key = event.public.topics[0].key
        target = self.repository.public_dir("clear") / "pieces" / participant.participant_key / topic_key
        target.mkdir(parents=True)
        (target / "index.html").write_text("old", encoding="utf-8")
        submissions = SubmissionService(self.service, SubmissionStorage(Path(self.temp.name) / "uploads"), object())
        with self.assertRaises(SubmissionServiceError):
            asyncio.run(
                submissions.clear_submission(
                    "123", topic=topic_key, now=datetime(2026, 1, 4, tzinfo=TZ)
                )
            )
        self.assertTrue((target / "index.html").exists())

    def test_christmas_private_data_and_blacklist_are_enforced(self):
        make_event(self.service, "xmas", "christmas")
        self.service.clock = lambda: datetime(2026, 1, 1, 12, tzinfo=TZ)
        asyncio.run(self.service.join("123"))
        asyncio.run(self.service.join("456"))
        christmas = ChristmasService(
            self.service,
            lambda _name: type(
                "Policy",
                (),
                {"generate": lambda _self, participants, blocked, config: [
                    GiftAssignment("123", "456")
                ]},
            )(),
        )
        asyncio.run(christmas.set_blacklist("456", ["123"]))
        asyncio.run(christmas.say("123", "hello"))
        with self.assertRaises(ChristmasServiceError):
            asyncio.run(christmas.reply("123", "missing", "reply"))
        private_messages = self.repository.private_dir("xmas") / "anonymous-messages.json"
        self.assertTrue(private_messages.exists())
        self.assertFalse((self.repository.public_dir("xmas") / "anonymous-messages.json").exists())
        with self.assertRaises(ChristmasServiceError):
            asyncio.run(christmas.gift_shuffle())

    def test_unregistered_anonymous_command_returns_chinese_ephemeral_error(self):
        make_event(self.service, "xmas-unregistered", "christmas")
        interaction = FakeInteraction("not-registered")
        cog = EventCog(None, repository=self.repository, event_service=self.service)
        asyncio.run(EventCog.anon_say.callback(cog, interaction, "hello"))
        self.assertTrue(interaction.response.done)
        self.assertEqual(len(interaction.followups), 1)
        content, options = interaction.followups[0]
        self.assertTrue(options["ephemeral"])
        self.assertIn("請先使用 `/event join` 報名", content)


if __name__ == "__main__":
    unittest.main()
