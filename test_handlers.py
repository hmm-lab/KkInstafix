"""Handler tests for bot.py using lightweight fakes — no real Telegram API.

These exercise the async update handlers (message dispatch, muted-user deletion,
command routing, text-spam dedup, the link-rewrite happy path) which the
pure-function suite in test_bot.py does not touch.
"""
import asyncio
import os

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token-not-used")

import bot  # noqa: E402


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeUser:
    def __init__(self, uid=1, first_name="Alice", username=None, is_bot=False):
        self.id = uid
        self.first_name = first_name
        self.last_name = None
        self.username = username
        self.is_bot = is_bot


class FakeChat:
    def __init__(self, chat_id=-1001, ctype="supergroup"):
        self.id = chat_id
        self.type = ctype


class _Member:
    def __init__(self, status, user):
        self.status = status
        self.user = user


class FakeBot:
    def __init__(self, admin=False):
        self.id = 999
        self.admin = admin
        self.sent = []          # messages sent via bot.send_message
        self.deleted = []       # (chat_id, message_id)

    async def send_message(self, chat_id, text, **kw):
        m = FakeMessage(text=text, chat=FakeChat(chat_id), message_id=1000 + len(self.sent), bot=self)
        self.sent.append(m)
        return m

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True

    async def get_chat_member(self, chat_id, user_id):
        status = "administrator" if self.admin else "member"
        return _Member(status, FakeUser(user_id, "Member"))


class FakeMessage:
    def __init__(self, text=None, user=None, chat=None, reply_to=None,
                 message_id=1, bot=None, caption=None):
        self.text = text
        self.caption = caption
        self.from_user = user
        self.chat = chat or FakeChat()
        self.chat_id = self.chat.id
        self.reply_to_message = reply_to
        self.message_id = message_id
        self._bot = bot
        self.replies = []
        self.deleted = False
        self.forward_origin = None
        self.forward_date = None
        self.new_chat_members = None
        self.sticker = None
        self.animation = None
        self.document = None

    async def reply_text(self, text, **kw):
        r = FakeMessage(text=text, chat=self.chat, message_id=9000 + len(self.replies), bot=self._bot)
        self.replies.append(r)
        return r

    async def delete(self):
        self.deleted = True
        return True


class FakeEntity:
    def __init__(self, type_, url=None):
        self.type = type_
        self.url = url


class FakeCallbackQuery:
    def __init__(self, data, message, user):
        self.data = data
        self.message = message
        self.from_user = user
        self.answers = []   # (text, show_alert)
        self.edits = []     # (text, kwargs)

    async def answer(self, text="", show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, **kw):
        self.edits.append((text, kw))


class FakeContext:
    def __init__(self, bot):
        self.bot = bot


class FakeUpdate:
    def __init__(self, message=None, update_id=1, callback_query=None):
        self.message = message
        self.edited_message = None
        self.channel_post = None
        self.callback_query = callback_query
        self.inline_query = None
        self.update_id = update_id


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Fresh DB caches and no background restriction task per test."""
    bot.init_db()
    bot._recent_mem.clear()
    bot._rate_mem.clear()
    bot.SEEN_UPDATES.clear()

    async def _noop(*a, **k):
        return None

    # The link-rewrite path spawns a restriction-check task; stub it out so tests
    # don't touch the network or leave pending tasks.
    monkeypatch.setattr(bot, "_warn_if_restricted", _noop)
    yield


def run(coro):
    return asyncio.run(coro)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_handle_message_rewrites_supported_link():
    fb = FakeBot()
    msg = FakeMessage(text="look https://twitter.com/u/status/1",
                      user=FakeUser(5, "Bob"), chat=FakeChat(-1101), bot=fb, message_id=1)
    run(bot.handle_message(FakeUpdate(msg, update_id=101), FakeContext(fb)))
    assert msg.deleted, "original message should be deleted"
    assert fb.sent, "a rewritten message should be sent"
    assert "vxtwitter.com" in fb.sent[0].text


def test_handle_message_ignores_unsupported_link():
    fb = FakeBot()
    msg = FakeMessage(text="https://example.org/page",
                      user=FakeUser(6, "Q"), chat=FakeChat(-1102), bot=fb, message_id=1)
    run(bot.handle_message(FakeUpdate(msg, update_id=102), FakeContext(fb)))
    assert not msg.deleted
    assert not fb.sent


def test_handle_message_deletes_muted_user():
    cid = -1103
    bot.mute_user(cid, 77)
    fb = FakeBot()
    msg = FakeMessage(text="anything", user=FakeUser(77, "M"), chat=FakeChat(cid), bot=fb, message_id=2)
    run(bot.handle_message(FakeUpdate(msg, update_id=103), FakeContext(fb)))
    assert msg.deleted
    bot.unmute_user(cid, 77)


def test_handle_message_public_command_version():
    fb = FakeBot()
    msg = FakeMessage(text="/version", user=FakeUser(9, "V"), chat=FakeChat(-1104), bot=fb, message_id=3)
    run(bot.handle_message(FakeUpdate(msg, update_id=104), FakeContext(fb)))
    assert msg.replies and bot.__version__ in msg.replies[0].text


def test_handle_message_admin_command_blocked_for_non_admin():
    fb = FakeBot(admin=False)
    msg = FakeMessage(text="/disable", user=FakeUser(12, "U"),
                      chat=FakeChat(-1105, "supergroup"), bot=fb, message_id=4)
    run(bot.handle_message(FakeUpdate(msg, update_id=105), FakeContext(fb)))
    assert msg.replies and "admin" in msg.replies[0].text.lower()


def test_handle_message_admin_command_allowed_for_admin():
    fb = FakeBot(admin=True)
    cid = -1106
    msg = FakeMessage(text="/disable", user=FakeUser(13, "A"),
                      chat=FakeChat(cid, "supergroup"), bot=fb, message_id=5)
    run(bot.handle_message(FakeUpdate(msg, update_id=106), FakeContext(fb)))
    assert bot.get_chat_settings(cid)["enabled"] == 0


def test_handle_message_dedupes_repeated_text():
    cid = -1107
    fb = FakeBot()

    def mk(mid):
        return FakeMessage(text="repeated spam line", user=FakeUser(11, "S"),
                           chat=FakeChat(cid), bot=fb, message_id=mid)

    first = mk(10)
    run(bot.handle_message(FakeUpdate(first, update_id=107), FakeContext(fb)))
    second = mk(11)
    run(bot.handle_message(FakeUpdate(second, update_id=108), FakeContext(fb)))
    assert not first.deleted
    assert second.deleted


def test_handle_message_skips_duplicate_update():
    fb = FakeBot()
    msg = FakeMessage(text="https://twitter.com/u/status/1",
                      user=FakeUser(5, "Bob"), chat=FakeChat(-1108), bot=fb, message_id=1)
    upd = FakeUpdate(msg, update_id=999)
    run(bot.handle_message(upd, FakeContext(fb)))
    sent_after_first = len(fb.sent)
    # Same update id again — must be ignored entirely.
    msg2 = FakeMessage(text="https://twitter.com/u/status/1",
                       user=FakeUser(5, "Bob"), chat=FakeChat(-1108), bot=fb, message_id=1)
    run(bot.handle_message(FakeUpdate(msg2, update_id=999), FakeContext(fb)))
    assert len(fb.sent) == sent_after_first
    assert not msg2.deleted


def test_handle_message_rate_limit_blocks_excess_links():
    cid = -1109
    fb = FakeBot()
    user = FakeUser(21, "R")
    # Default rate limit is 5 links / 30s; the 6th link in the window is dropped.
    for i in range(5):
        m = FakeMessage(text=f"https://twitter.com/u/status/{i}", user=user,
                        chat=FakeChat(cid), bot=fb, message_id=i + 1)
        run(bot.handle_message(FakeUpdate(m, update_id=200 + i), FakeContext(fb)))
    rewrites = len(fb.sent)
    blocked = FakeMessage(text="https://twitter.com/u/status/999", user=user,
                          chat=FakeChat(cid), bot=fb, message_id=99)
    run(bot.handle_message(FakeUpdate(blocked, update_id=999), FakeContext(fb)))
    # No new rewrite was sent and the message was not deleted as a rewrite.
    assert len(fb.sent) == rewrites
    assert not blocked.deleted


# ── Callback handler (cycle button) ──────────────────────────────────────────

def _cycle_msg(fb, text, message_id=7, chat_id=-1201, entities=None):
    msg = FakeMessage(text=text, user=FakeUser(5, "Bob"),
                      chat=FakeChat(chat_id), bot=fb, message_id=message_id)
    msg.parse_entities = lambda types=None: (entities or {})
    return msg


def test_cycle_provider_edits_to_next_provider_from_plain_url():
    fb = FakeBot()
    msg = _cycle_msg(fb, "🐦 https://vxtwitter.com/u/status/1")
    cq = FakeCallbackQuery("e:twitter:1", msg, FakeUser(5, "Bob"))
    run(bot.handle_callback(FakeUpdate(callback_query=cq), FakeContext(fb)))
    assert cq.edits, "the message should be edited to the next provider"
    # twitter options order: vx, fx, ... → index 1 is fx
    assert "fxtwitter.com" in cq.edits[0][0]
    assert cq.answers, "the callback must be answered to clear the spinner"


def test_cycle_provider_uses_text_link_entity_and_preserves_label():
    fb = FakeBot()
    ent = FakeEntity("text_link", url="https://vxtwitter.com/u/status/1")
    msg = _cycle_msg(fb, "Bob", entities={ent: "Bob"})
    cq = FakeCallbackQuery("e:twitter:2", msg, FakeUser(5, "Bob"))
    run(bot.handle_callback(FakeUpdate(callback_query=cq), FakeContext(fb)))
    assert cq.edits
    text = cq.edits[0][0]
    assert "fixvx.com" in text          # twitter options index 2
    assert ">Bob</a>" in text           # the display label is preserved


def test_cycle_provider_bad_platform_answers_alert():
    fb = FakeBot()
    msg = _cycle_msg(fb, "🐦 https://vxtwitter.com/u/status/1")
    cq = FakeCallbackQuery("e:notaplatform:0", msg, FakeUser(5, "Bob"))
    run(bot.handle_callback(FakeUpdate(callback_query=cq), FakeContext(fb)))
    assert not cq.edits
    assert cq.answers and cq.answers[0][1] is True  # show_alert


def test_callback_test_button_answers():
    fb = FakeBot()
    msg = _cycle_msg(fb, "x")
    cq = FakeCallbackQuery("test", msg, FakeUser(1, "A"))
    run(bot.handle_callback(FakeUpdate(callback_query=cq), FakeContext(fb)))
    assert cq.answers and "works" in cq.answers[0][0].lower()


def test_callback_menu_requires_admin():
    fb = FakeBot(admin=False)
    msg = FakeMessage(text="menu", user=FakeUser(1, "A"),
                      chat=FakeChat(-1203, "supergroup"), bot=fb, message_id=1)
    cq = FakeCallbackQuery("m:close", msg, FakeUser(1, "A"))
    run(bot.handle_callback(FakeUpdate(callback_query=cq), FakeContext(fb)))
    assert cq.answers and "admin" in cq.answers[0][0].lower()
    assert not cq.edits
