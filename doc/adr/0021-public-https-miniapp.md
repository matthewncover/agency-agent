# ADR-0021: Public HTTPS surface for a Telegram Mini App (Caddy, path routing)

**Status:** Accepted

## Context
Until now the system polled Telegram and had no inbound port and no public URL. That posture was never an ADR. It lived in `deploy/README.md` ("Decisions baked in"), `doc/build/B8-vps-deploy.md`, and the header of `deploy/goal-bot.service`.

The v2 morning checklist needs a page that Telegram can load over HTTPS. Each person keeps a private list and ticks it off. A "Complete morning" button then posts a short summary to the shared group chat. Telegram Mini Apps are the lowest-friction way to show that page inside the chat, and they need a public HTTPS URL. The page also has to know who is looking at it without a login step.

## Options weighed

1. **Caddy on the VPS with a domain (chosen).** Caddy gets and renews Let's Encrypt certs on its own, and its config is a few lines. The origin is exposed and ports 80/443 must be open. It costs a domain renewal.
2. **Cloudflare Tunnel.** No open ports, and it hides the origin. But DNS moves to Cloudflare, `cloudflared` becomes another daemon to run, and Cloudflare terminates TLS, so it sees every request in plaintext.
3. **Tailscale Funnel.** No domain needed. But the URL is a `ts.net` name tied to the machine and tailnet, and renaming either breaks the registered Mini App URL. Traffic relays through a third party, and it adds another daemon and account.
4. **Plain URL with a secret token instead of a Mini App.** Simplest server side. Rejected: a token in the URL leaks through browser history, link previews and forwarded messages, and it is identity by possession rather than by Telegram account.

## Decision
- **Caddy with automatic Let's Encrypt TLS on `trendingupward.space`.** Caddy is the only public listener. Apps bind `127.0.0.1` and Caddy reverse-proxies to them. Config lives in `deploy/Caddyfile`.
- **Path-based routing.** The Mini App is served at `/morning/` (Caddy strips the prefix and proxies to `127.0.0.1:8081`). Future apps get their own `handle_path /<app>/*` block. Anything else returns 404.
- **Identity is Telegram Mini App initData, verified server-side.** The server checks the HMAC with secret key `HMAC_SHA256("WebAppData", bot_token)`, rejects an `auth_date` older than 24 h, and maps the Telegram user id to a person via the existing `TELEGRAM_USER_MAP`. No person id or token appears in the URL.
- **A separate bot and process.** The `routines` package (systemd unit `routines`) has its own bot token and runs PTB polling, the aiohttp server and APScheduler on one event loop. It shares the database, `HEARTBEAT_URL` and `TELEGRAM_USER_MAP` with goal-bot.
- **Ports 80/tcp and 443/tcp are opened** on the VPS firewall and any Vultr firewall group.

## Consequences
- **New inbound surface.** Only Caddy listens publicly; the app binds localhost, so the exposed surface is Caddy plus whatever the proxied app accepts. Every request to the app must carry valid initData.
- **Domain renewal is now an ops dependency.** If the domain lapses, the Mini App goes dark. Auto-renew is on. The previous domain lapsed and was lost, which is why this is called out.
- **A dev-only auth bypass exists.** `ROUTINES_DEV_PERSON_ID` skips initData so the UI can be worked on in a plain browser. The server refuses to start with it unless bound to `127.0.0.1`, and it is never set in prod.
- **Webhooks become possible but are not adopted.** Both bots keep polling. Switching to webhooks would be a separate decision.
- **Naming.** The package is named `routines` for what it does today. If goal-bot v2 ever moves into this process (only one process can poll a given bot token), rename the package, unit and env prefix at that point.
