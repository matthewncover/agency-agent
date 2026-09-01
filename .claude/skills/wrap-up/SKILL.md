---
name: wrap-up
description: End-of-session close-out. Comb the whole chat for loose ends and give a verdict on whether the session can be marked done. Use when the user asks "any loose ends?", "are we done?", "can I close this session?", or invokes /wrap-up.
---

# Session wrap-up

Re-read the entire conversation and answer one question honestly: is anything
unfinished? Lead with the verdict, then the evidence.

## Sweep, in order

1. **Commitments in the transcript.** Anything phrased as "I'll ...", "once you
   ..., I'll ...", "say the word and ...", offers the user accepted, questions
   the user asked that never got a direct answer, and decisions explicitly
   deferred ("decide before X") that were never decided.
2. **Working tree.** `git status --short` + `git log --oneline -3`. Flag:
   uncommitted or untracked files, staged-but-uncommitted work, and
   committed-but-unpushed commits (push is always the human's step in this
   repo). Label each item *session-created* or *pre-existing*; pre-existing
   mess is mentioned once, never counted against the session.
3. **Half-finished state changes.** Anything the session started but did not
   land: env edited without a service restart, a deploy waiting on a push, DB
   rows changed but never verified, a tunnel or LaunchAgent kicked into a
   temporary state, a migration written but not applied.
4. **Unverified claims.** Code changed but tests never run; a fix asserted
   without evidence; a prod change with no journal/DB check afterward. Run the
   cheap verification now rather than listing it as a loose end.
5. **Doc and memory sync.** If behavior changed: did ADRs / skills / env
   examples / CLAUDE.md keep up (repo convention)? Should persistent memory be
   updated, and does anything in memory now contradict what this session did?

## Verdict

Close with one of:

- **"Good to mark done."** Nothing unfinished, or only pre-existing items the
  session never touched (name them in one line each so they don't hide).
- **A short ranked list**, blocking first, optional last. For each: what it is,
  whose move it is (user vs a future session), and the one command or action
  that closes it.

For loose ends that will outlive the session, offer to capture them durably
(a task-tracker personal task, or a MATTHEW-TODO line) instead of letting the
list scroll away.

## Rules

- **Do not invent work.** No manufactured nice-to-haves dressed as loose ends;
  if something is optional, say "optional" and move on. A clean session gets a
  clean two-line answer.
- Fix trivial items on the spot (a one-command verification, a memory update)
  rather than reporting them as open.
- Respect repo boundaries while sweeping: read-only git, no push, no prod
  mutations; VPS checks are read-only and announced first.
