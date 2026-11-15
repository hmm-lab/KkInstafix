"""Regression coverage for Telegram SDK validation and failed deliveries."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from telegram import Bot, LinkPreviewOptions
from telegram.error import Forbidden, RetryAfter, TimedOut

import bot
import helpers
from test_handlers import (
    FakeBot, FakeChat, FakeContext, FakeMessage, FakeUpdate, FakeUser, _isolate,
)


def test_preview_send_passes_real_telegram_sdk_validation(monkeypatch):
    send = AsyncMock(return_value=object())
    monkeypatch.setattr(Bot, '_send_message', send)
    client = Bot('123:fake', request=object(), get_updates_request=object())
    preview = LinkPreviewOptions(url='https://example.org')
    result = asyncio.run(helpers.safe_send_text(
        FakeContext(client), 1, 'https://example.org', link_preview_options=preview,
    ))
    assert result is send.return_value
    assert send.await_args.kwargs['link_preview_options'] == preview


def test_delete_calls_telegram_once():
    fb = FakeBot()
    msg = FakeMessage(bot=fb)
    asyncio.run(helpers.safe_delete(FakeContext(fb), msg.chat_id, 1, message=msg))
    assert len(fb.deleted) + int(msg.deleted) == 1


def test_failed_rewrite_preserves_original_and_allows_retry(monkeypatch):
    async def fail(**kwargs):
        raise RuntimeError('send unavailable')
    async def fix(*args):
        return args[0].replace('twitter.com', 'vxtwitter.com'), 'twitter', args[0], args[0].replace('twitter.com', 'vxtwitter.com')
    monkeypatch.setattr(bot, 'fix_url', fix)
    fb = FakeBot()
    fb.send_message = fail
    msg = FakeMessage(text='https://twitter.com/u/status/1', user=FakeUser(), bot=fb)
    asyncio.run(bot.handle_message(FakeUpdate(msg), FakeContext(fb)))
    assert not msg.deleted
    assert not fb.deleted
    assert not any(k[0] == 'fix' for k in bot._recent_mem)


def test_rewrite_is_sent_before_deletion(monkeypatch):
    events = []
    fb = FakeBot()
    original_send = fb.send_message
    async def send(*args, **kwargs):
        events.append('send')
        return await original_send(*args, **kwargs)
    fb.send_message = send
    msg = FakeMessage(text='https://twitter.com/u/status/2', user=FakeUser(), bot=fb)
    async def delete():
        events.append('delete')
    msg.delete = delete
    async def fixed(*args):
        return ('https://vxtwitter.com/u/status/2', True, 'https://vxtwitter.com/u/status/2', 'twitter', 'https://vxtwitter.com/u/status/2', 1, ['twitter'], msg.text)
    monkeypatch.setattr(bot, 'process_text', fixed)
    asyncio.run(bot.handle_message(FakeUpdate(msg), FakeContext(fb)))
    assert events == ['send', 'delete']


def test_rewrite_button_uses_registered_callback_protocol(monkeypatch):
    async def fixed(*args):
        return ('https://vxtwitter.com/u/status/3', True, 'https://vxtwitter.com/u/status/3', 'twitter', 'https://vxtwitter.com/u/status/3', 1, ['twitter'], 'https://twitter.com/u/status/3')
    monkeypatch.setattr(bot, 'process_text', fixed)
    fb = FakeBot()
    captured = []
    original_send = fb.send_message
    async def send(*args, **kwargs):
        captured.append(kwargs)
        return await original_send(*args, **kwargs)
    fb.send_message = send
    msg = FakeMessage(text='https://twitter.com/u/status/3', user=FakeUser(), bot=fb)
    asyncio.run(bot.handle_message(FakeUpdate(msg), FakeContext(fb)))
    assert captured[0]['reply_markup'].inline_keyboard[0][0].callback_data.startswith('e:twitter:')


@pytest.mark.parametrize('kind, expected', [
    ('message', bot.handle_message),
    ('edited_message', bot.handle_edit),
    ('channel_post', bot.handle_channel_post),
])
def test_update_dispatch_reaches_correct_handler(kind, expected):
    from telegram import Update
    from types import SimpleNamespace
    registered = []
    app = SimpleNamespace(add_handler=registered.append, add_error_handler=lambda h: None)
    bot.register_update_handlers(app)
    update = Update.de_json({'update_id': 1, kind: {
        'message_id': 1, 'date': 0, 'text': 'https://twitter.com/u/status/1',
        'chat': {'id': -1001, 'type': 'channel' if kind == 'channel_post' else 'supergroup'},
    }}, None)
    selected = next(h for h in registered if h.check_update(update))
    assert selected.callback is expected


@pytest.mark.parametrize('error', [
    Forbidden('no permission'),
    RetryAfter(20),
    TimedOut(),
])
def test_transport_and_permission_failures_do_not_burst_fallbacks(error):
    fb = FakeBot()
    fb.send_message = AsyncMock(side_effect=error)
    result = asyncio.run(helpers.send_rewrite(
        FakeContext(fb), -1001, 'formatted', 'https://vxtwitter.com/u/status/1',
    ))
    assert result is None
    assert fb.send_message.await_count == 1


def test_bad_format_falls_back_to_fixed_link_without_failure_message():
    from telegram.error import BadRequest
    fb = FakeBot()
    delivered = object()
    fb.send_message = AsyncMock(side_effect=[BadRequest('cannot parse entities'), delivered])
    result = asyncio.run(helpers.send_rewrite(
        FakeContext(fb), -1001, 'formatted', 'https://vxtwitter.com/u/status/1',
    ))
    assert result is delivered
    assert fb.send_message.await_args.kwargs['text'] == 'https://vxtwitter.com/u/status/1'
    assert fb.send_message.await_args.kwargs['parse_mode'] is None


@pytest.mark.parametrize('kind', ['caption', 'edit', 'channel'])
def test_failed_delivery_releases_dedup_for_other_update_types(monkeypatch, kind):
    fb = FakeBot()
    fb.send_message = AsyncMock(side_effect=Forbidden('no permission'))
    msg = FakeMessage(text='https://twitter.com/u/status/4',
                      caption='https://twitter.com/u/status/4', user=FakeUser(), bot=fb)
    if kind == 'caption':
        update, handler = FakeUpdate(message=msg), bot.handle_caption
    elif kind == 'edit':
        update, handler = FakeUpdate(edited_message=msg), bot.handle_edit
    else:
        update, handler = FakeUpdate(channel_post=msg), bot.handle_channel_post
    asyncio.run(handler(update, FakeContext(fb)))
    assert not msg.deleted
    assert not any(k[0] == 'fix' for k in bot._recent_mem)


def test_rewrite_escapes_sender_name_for_html_delivery():
    # The production formatter must escape user names before HTML delivery.
    fb = FakeBot()
    msg = FakeMessage(text='https://twitter.com/u/status/5',
                      user=FakeUser(first_name='Alice <3 & Bob'), bot=fb)
    asyncio.run(bot.handle_message(FakeUpdate(msg), FakeContext(fb)))
    assert 'Alice &lt;3 &amp; Bob' in fb.sent[0].text
