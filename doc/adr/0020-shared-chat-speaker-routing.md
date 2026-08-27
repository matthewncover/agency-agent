# ADR-0020: The shared group chat is the goal surface; identity routes by speaker, never by chat

**Status:** Accepted

## Context
The product vision has always been one shared chat for the couple — the behavior spec's "no in-app social mechanics" decision (D-15) is justified by "it's already a shared chat," and the one-voice decision (spec §12) assumes both people read the same conversation. Transparency and accountability come from goal talk happening in front of the partner; individual 1:1 chats are reserved for personal task tracking, where goal traffic would be noise and task traffic would be noise in the goal chat.

The B7 runtime, however, shipped chat-scoped identity: `TELEGRAM_CHAT_MAP` maps each chat id to exactly one person, sessions are keyed by chat id, and the speaker's `from_user` is never consulted. In a group chat containing both partners, everything anyone says is attributed to the chat's single mapped person — the second person cannot exist on that surface at all, and worse, their words would silently act as the first person's.

Two non-negotiables make misattribution more than a UX bug. ENGAGEMENT-NOT-FAILURE infers engaged-vs-silent from whether the person answered their own touchpoint; if a partner's reply counts as the person answering, silence stops being null and the reassessment counter corrupts. And outcome logging by proxy would let one partner mark the other's items done or not done.

## Decision
1. **Identity comes from the speaker; the chat only defines the surface.** A new `TELEGRAM_USER_MAP` (`telegramuserid:personid,...`) resolves the acting person from the message's `from_user.id`. When it is configured, it decides identity in every chat type. `TELEGRAM_CHAT_MAP` keeps two jobs: membership (which chats the bot lives in) and send targets (where each person's scheduled morning goes) — and it may now map the same chat id to several persons, which is what makes a chat a shared surface.
2. **Nobody can speak for or act as the other person — a hard guardrail, decided by the humans.** A message only ever routes to the speaker's own session (sessions are keyed by `(chat_id, person_id)`). A known chat with an unmapped speaker resolves to no one: the message is ignored and logged, never attributed to another person. There is no proxy path — replying inside the partner's morning thread still routes to the speaker's own session.
3. **Scheduled sends into a shared chat are name-labeled** (`Jade:\n...`) so it is obvious whose morning each message is; solo chats stay unadorned. `/whoami` answers in any known chat, even for unmapped speakers, and includes `user_id` — that is exactly the onboarding moment where someone needs their id.
4. **Legacy routing survives unchanged.** With no user map configured, single-person chats route by chat id exactly as before (A7/B7 back-compat). A multi-person chat without a user map resolves nobody and warns loudly at build time.

Deliberately **not** built: reply-target routing (letting a reply inside the partner's thread act on that thread). It was considered and rejected — even a hybrid ("context from the thread, identity from the speaker") reopens the door to partner words becoming the other person's data. Partner commentary stays human-to-human, which D-15 already prefers.

## Consequences
- Wiring the couple's shared chat becomes: `TELEGRAM_CHAT_MAP=<groupchatid>:1,<groupchatid>:2` plus `TELEGRAM_USER_MAP=<uid1>:1,<uid2>:2`. Each person's telegram user id is required once, at wiring time (readable from the `auth rejected: known chat, unmapped user_id` journal line or `/whoami`).
- Both morning jobs post into the same chat at each person's own local time; with matching timezones they arrive back-to-back, distinguished by the name label.
- NULL-TOLERANCE and ENGAGEMENT-NOT-FAILURE stay sound in a shared chat: only a person's own messages can count as their engagement or log their outcomes.
- The explicit-addressing gate for groups (reply-to-bot or @mention) is unchanged and remains the noise control.
- A future third surface (e.g. a household group with a child, ADR-0012's expansion case) is config, not code: add the chat pair(s) and the new speaker to the maps.
