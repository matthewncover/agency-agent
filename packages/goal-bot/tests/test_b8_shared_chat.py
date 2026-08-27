"""B8 — shared-chat speaker routing: one group chat, identity from the
speaker's telegram user id, hard guardrail that nobody can act as the other."""

from agency_profile.domain.entities import Person
from goal_bot.config import Settings
from goal_bot.infrastructure.telegram_adapter import TelegramAdapter

_TOKEN = "123456:ABCdefGHIjklMNOpqrs"
_SHARED_CHAT = -1004398904561


def _shared_adapter():
    persons = {
        1: Person(display_name="Matthew", timezone="America/Phoenix"),
        2: Person(display_name="Jade", timezone="America/Phoenix"),
    }
    return TelegramAdapter(
        token=_TOKEN,
        chat_person=[(_SHARED_CHAT, 1), (_SHARED_CHAT, 2)],
        persons=persons,
        service=None,
        scheduler=None,
        user_person={9001: 1, 9002: 2},
    )


# --- config -----------------------------------------------------------------


def test_user_map_parses_pairs():
    s = Settings(telegram_user_map="9001:1,9002:2")
    assert s.user_person_pairs() == [(9001, 1), (9002, 2)]


def test_user_map_empty_when_unconfigured():
    assert Settings(telegram_user_map="").user_person_pairs() == []


def test_chat_map_allows_same_chat_for_two_persons():
    s = Settings(telegram_chat_map=f"{_SHARED_CHAT}:1,{_SHARED_CHAT}:2")
    assert s.chat_person_pairs() == [(_SHARED_CHAT, 1), (_SHARED_CHAT, 2)]


# --- speaker routing --------------------------------------------------------


def test_speaker_decides_identity_in_shared_chat():
    a = _shared_adapter()
    assert a.person_for(_SHARED_CHAT, user_id=9001) == 1
    assert a.person_for(_SHARED_CHAT, user_id=9002) == 2


def test_unmapped_speaker_in_known_chat_is_ignored_not_misattributed():
    a = _shared_adapter()
    assert a.person_for(_SHARED_CHAT, user_id=7777) is None


def test_unknown_chat_rejected_even_for_mapped_speaker():
    a = _shared_adapter()
    assert a.person_for(999, user_id=9001) is None


def test_user_map_overrides_chat_routing_everywhere():
    # with a user map, even a single-person chat routes by speaker — identity
    # never comes from the chat once speakers are mapped
    persons = {1: Person(display_name="A", timezone="UTC")}
    a = TelegramAdapter(
        token=_TOKEN,
        chat_person=[(111, 1)],
        persons=persons,
        service=None,
        scheduler=None,
        user_person={9001: 1},
    )
    assert a.person_for(111, user_id=9001) == 1
    assert a.person_for(111, user_id=7777) is None


def test_shared_chat_without_user_map_resolves_nobody():
    persons = {
        1: Person(display_name="A", timezone="UTC"),
        2: Person(display_name="B", timezone="UTC"),
    }
    a = TelegramAdapter(
        token=_TOKEN,
        chat_person=[(_SHARED_CHAT, 1), (_SHARED_CHAT, 2)],
        persons=persons,
        service=None,
        scheduler=None,
    )
    assert a.person_for(_SHARED_CHAT, user_id=9001) is None


# --- send targets + labeling ------------------------------------------------


def test_both_persons_send_into_the_shared_chat():
    a = _shared_adapter()
    assert a.chat_for_person(1) == _SHARED_CHAT
    assert a.chat_for_person(2) == _SHARED_CHAT


def test_scheduled_send_is_name_labeled_in_shared_chat():
    a = _shared_adapter()
    assert a.is_shared_chat(_SHARED_CHAT) is True
    assert a.label_outbound(_SHARED_CHAT, 2, "morning!") == "Jade:\nmorning!"


def test_solo_chat_send_is_unlabeled():
    persons = {1: Person(display_name="A", timezone="UTC")}
    a = TelegramAdapter(
        token=_TOKEN,
        chat_person=[(111, 1)],
        persons=persons,
        service=None,
        scheduler=None,
    )
    assert a.is_shared_chat(111) is False
    assert a.label_outbound(111, 1, "morning!") == "morning!"
