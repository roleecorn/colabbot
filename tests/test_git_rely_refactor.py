import asyncio
import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cmds.gitRely.event_service import EventService, EventServiceError
from cmds.gitRely.christmas_service import ChristmasService, ChristmasServiceError
from cmds.gitRely.models import EventStatus, event_status
from cmds.gitRely.models import GiftAssignment
from cmds.gitRely.repositories import EventRepository
from cmds.gitRely.public_index import PublicEventIndex
from cmds.gitRely.startup import EventStartupError, validate_active_event_configuration
from cmds.gitRely.storage import SubmissionStorage
from cmds.gitRely.submission_service import SubmissionService, SubmissionServiceError
from cmds.gitRely.event_cog import EventCog
from cmds.gitRely.publisher import GitPublishError, GitPublisher
from core.classes import Cog_extension, GUILD_ID


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
        self.guild = type("Guild", (), {"id": 1})()
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

    def test_aa_fanclub_check_handles_interactions_without_a_guild(self):
        self.assertFalse(Cog_extension.bIsAAFanclub(SimpleNamespace()))
        self.assertFalse(Cog_extension.bIsAAFanclub(SimpleNamespace(guild=None)))
        self.assertTrue(
            Cog_extension.bIsAAFanclub(SimpleNamespace(guild=SimpleNamespace(id=GUILD_ID)))
        )
        self.assertFalse(
            Cog_extension.bIsAAFanclub(SimpleNamespace(guild=SimpleNamespace(id=123)))
        )

    def test_christmas_commands_are_registered_under_one_group(self):
        self.assertEqual(EventCog.christmas_group.name, "christmas")
        self.assertEqual(
            {command.name for command in EventCog.christmas_group.commands},
            {
                "anonsay",
                "anonreply",
                "blacklist",
                "giftshuffle",
                "finalize",
                "giftme",
                "publishworks",
            },
        )

    def test_unexpected_errors_get_actionable_messages_by_failure_type(self):
        cases = (
            (ConnectionError("secret endpoint"), "無法連線至必要服務"),
            (TimeoutError("secret endpoint"), "連線等待逾時"),
            (PermissionError("private path"), "無法存取所需的活動檔案或目錄"),
            (FileNotFoundError("private path"), "找不到必要的活動資料或檔案"),
            (RuntimeError("private details"), "系統內部處理失敗"),
        )
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                message = EventCog._unexpected_error_message(error, "AB12CD34")
                self.assertIn(expected, message)
                self.assertIn("AB12CD34", message)
                self.assertNotIn(str(error), message)

    def test_status_boundaries_are_derived(self):
        event = make_event(self.service)
        self.assertEqual(event_status(event.private, datetime(2025, 12, 31, 23, 59, tzinfo=TZ)), EventStatus.SCHEDULED)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 1, tzinfo=TZ)), EventStatus.REGISTRATION_OPEN)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 2, tzinfo=TZ)), EventStatus.WAITING_SUBMISSION)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 3, tzinfo=TZ)), EventStatus.SUBMISSION_OPEN)
        self.assertEqual(event_status(event.private, datetime(2026, 1, 4, tzinfo=TZ)), EventStatus.CLOSED)

    def test_startup_check_rejects_invalid_active_event(self):
        make_event(self.service, "startup-invalid")
        private_path = self.repository.private_path("startup-invalid")
        private = json.loads(private_path.read_text(encoding="utf-8"))
        private["submission_starts_at"] = private["registration_starts_at"]
        private_path.write_text(json.dumps(private), encoding="utf-8")

        with self.assertRaises(EventStartupError):
            validate_active_event_configuration(self.repository)

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

    def test_existing_html_is_preferred_over_generated_gallery(self):
        root = Path(self.temp.name) / "submission"
        root.mkdir()
        (root / "z.html").write_text("z", encoding="utf-8")
        (root / "a.html").write_text("a", encoding="utf-8")
        (root / "cover.png").write_bytes(b"image")

        selected = SubmissionStorage.generate_gallery(root, "ignored title")

        self.assertEqual(selected, root / "a.html")
        self.assertFalse((root / "index.html").exists())

        (root / "index.html").write_text("index", encoding="utf-8")
        selected = SubmissionStorage.generate_gallery(root, "ignored title")
        self.assertEqual(selected, root / "index.html")
        self.assertEqual((root / "index.html").read_text(encoding="utf-8"), "index")

    def test_replace_directory_keeps_rollback_backup_outside_public_repository(self):
        root = Path(self.temp.name)
        repo = root / "public"
        target = repo / "pieces" / "participant" / "topic"
        target.mkdir(parents=True)
        (target / "old.txt").write_text("old", encoding="utf-8")
        staged = root / "uploads" / "request" / "submission"
        staged.mkdir(parents=True)
        (staged / "new.txt").write_text("new", encoding="utf-8")

        backup = SubmissionStorage(root / "uploads").replace_directory(staged, target)

        self.assertIsNotNone(backup)
        self.assertEqual(Path(backup).parent, staged.parent)
        self.assertNotIn(repo, Path(backup).parents)
        self.assertEqual((target / "new.txt").read_text(encoding="utf-8"), "new")
        self.assertEqual((Path(backup) / "old.txt").read_text(encoding="utf-8"), "old")

    def test_publisher_excludes_internal_backup_paths_from_git_add(self):
        publisher = GitPublisher()

        class Completed:
            returncode = 0

        with patch("cmds.gitRely.publisher.subprocess.run", return_value=Completed()) as run:
            publisher._publish_sync(Path(self.temp.name), "test")

        self.assertEqual(
            run.call_args_list[1].args[0],
            ["git", "add", "--update", "--", "."],
        )
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["git", "add", "--all", "--", ".", ":(exclude)**/*.backup-*"],
        )

    def test_publisher_rolls_back_local_commit_when_pull_fails(self):
        publisher = GitPublisher()

        class Completed:
            def __init__(self, returncode=0):
                self.returncode = returncode

        results = iter(
            [
                Completed(),  # rev-parse
                Completed(),  # add --update
                Completed(),  # add --all
                Completed(),  # commit
                Completed(1),  # pull --rebase
                Completed(),  # reset --mixed
            ]
        )
        def fake_run(*args, **kwargs):
            process = next(results)
            if args[0] == ["git", "rev-parse", "HEAD"]:
                kwargs["stdout"].write(b"before-head\n")
            return process

        with patch(
            "cmds.gitRely.publisher.subprocess.run",
            side_effect=fake_run,
        ) as run:
            with self.assertRaises(GitPublishError):
                publisher._publish_sync(Path(self.temp.name), "test")

        self.assertEqual(
            run.call_args_list[-1].args[0],
            ["git", "reset", "--mixed", "before-head"],
        )

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
        work_index = root / "public" / "upload" / "data" / "workUserMap.json"
        self.assertEqual(json.loads(work_index.read_text(encoding="utf-8"))[0]["title"], "old")
        with self.assertRaises(SubmissionServiceError):
            asyncio.run(
                submissions.upload_archive(
                    "123", archive_two, topic="one", title="new", now=datetime(2026, 1, 3, tzinfo=TZ)
                )
            )
        target = self.repository.public_dir("upload") / "pieces" / participant.participant_key
        self.assertEqual((target / event.public.topics[0].key / "old.png").read_bytes(), b"old")
        self.assertFalse((target / event.public.topics[0].key / "new.png").exists())
        self.assertEqual(json.loads(work_index.read_text(encoding="utf-8"))[0]["title"], "old")

    def test_public_index_orders_each_participant_before_the_next(self):
        event = make_event(self.service, "summer-order")
        self.service.clock = lambda: datetime(2026, 1, 1, 12, tzinfo=TZ)
        first = asyncio.run(self.service.join("123", "User A"))
        second = asyncio.run(self.service.join("456", "User B"))
        event = asyncio.run(self.service.load_active())
        index = PublicEventIndex(self.repository)

        index.upsert_work(event, first, event.public.topics[1], "A-2")
        index.upsert_work(event, second, event.public.topics[0], "B-1")
        index.upsert_work(event, first, event.public.topics[0], "A-1")

        works = json.loads(
            (self.repository.public_dir("summer-order") / "data" / "workUserMap.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(
            [(item["name"], item["topic"]) for item in works],
            [("User A", "one"), ("User A", "two"), ("User B", "one")],
        )
        public_text = json.dumps(works, ensure_ascii=False)
        self.assertNotIn("123", public_text)
        self.assertNotIn("456", public_text)
        self.assertEqual(first.participant_key, works[0]["hashId"])
        self.assertEqual(second.participant_key, works[-1]["hashId"])
        self.assertEqual(
            PublicEventIndex.work_url(first.participant_key, "one"),
            f"pieces/{first.participant_key}/one/",
        )
        self.assertEqual(
            PublicEventIndex.work_url(first.participant_key, "one", "reader/main.html"),
            f"pieces/{first.participant_key}/one/reader/main.html",
        )

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
