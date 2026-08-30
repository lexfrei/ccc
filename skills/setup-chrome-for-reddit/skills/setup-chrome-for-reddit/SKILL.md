---
name: setup-chrome-for-reddit
description: >
  Set up (or repair) the Playwright MCP browser on this host so it can reach Reddit and other bot-hostile sites, and log into Reddit when needed.
  TRIGGER: invoke when the user asks to browse Reddit, when Reddit or search engines return 403 / "blocked by network security" / captcha walls from the MCP browser, or when the playwright MCP is missing or freshly reinstalled.
  DO NOT TRIGGER for ordinary browsing that already works, and NEVER to solve captchas — captcha walls are a hard stop.
---

# Setup Chrome (Playwright MCP) for Reddit

## Background facts (checked 2026-08-30)

- Reddit serves 403 + "You've been blocked by network security" to the stock Playwright headless browser on the FIRST document request — server-side detection of the `HeadlessChrome` UA token, before any JS runs. Same IP with a normal desktop UA gets 200.
- Overriding the UA via the MCP's own `--user-agent` flag is sufficient to get normal pages, including the old.reddit login form. No stealth plugins needed.
- Logged-out Reddit is effectively dead anyway: unauthenticated `.json` endpoints return an HTML shell, and old.reddit requires login for search (`reason=lor2`). A real account login through the normal form works. Reportedly the cause is Reddit closing self-service Data API access and locking unauthenticated endpoints — that part comes from write-ups, not from anything measured here.
- Most search engines (Google, DDG, Brave, Mojeek, Startpage) captcha or 403 the headless browser. Bing lets it through but mangles quoted/OR queries. For finding thread URLs prefer the built-in WebSearch tool, then open the URLs in the browser.

## Step 1: Ensure the MCP registration

Check with `claude mcp list`: the `playwright` entry should carry a `--user-agent` argument without the word "Headless". `list` prints the full command but not the scope, so before changing anything read `claude mcp get playwright`, which prints both — an entry in a scope you did not expect means a second registration is shadowing this one.

Re-registering rewrites a config that applies to every project, and the existing entry may carry flags someone chose deliberately (`--user-data-dir`, `--caps`, `--allowed-origins`, `--output-dir`). Take the args from `claude mcp get`, keep every one of them, replace only the user-agent, then show the user the current and proposed commands and wait for approval before running anything:

```bash
claude mcp remove playwright  # no --scope, so it hits whichever scope holds it
claude mcp add --scope <same scope it had> playwright -- docker run --interactive --rm --init <docker flags> mcr.microsoft.com/playwright/mcp <server flags> --user-agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<major>.0.0.0 Safari/537.36"
```

Two placeholders, because the split matters: `--volume` and anything else docker consumes goes before the image name, while `--user-data-dir`, `--caps`, `--allowed-origins` and `--output-dir` belong to the MCP server and go after it. Re-register into the scope the entry already had — `user` for a fresh setup, but moving an existing `local` or `project` entry to `user` silently widens where it applies.

Fill `<major>` from the image rather than from this file, and keep it within a few major versions of the real Chromium:

```bash
docker run --rm --entrypoint /bin/sh mcr.microsoft.com/playwright/mcp -c 'ls -d /ms-playwright/chromium*'
docker run --rm --entrypoint /ms-playwright/chromium-<build>/chrome-linux64/chrome mcr.microsoft.com/playwright/mcp --version
```

After changing the registration, the running session still talks to the OLD container. Ask the user to run `/mcp reconnect playwright`, then continue. If the browser still returns 403 while `claude mcp get playwright` already shows the new user-agent, the config is right and the running container is stale — reconnect again.

## Step 2: Log into Reddit (only when the task needs Reddit)

Credentials: ask the user. Never store them in this skill, in memory, or in any file. A password pasted into chat lands in the session log, so say so afterwards and recommend rotating it. Where the host allows a persistent profile (`--user-data-dir`, below), one manual login there keeps the password out of the conversation entirely.

1. `browser_navigate` to the target old.reddit URL. Getting redirected to `old.reddit.com/login/?reason=lor2` is expected.
2. Dismiss the cookie dialog ("Reject Optional Cookies").
3. Fill "Email or username" + "Password", click "Log In".
4. Verify via `browser_network_requests` filtered to `login`: success is `POST /svc/shreddit/account/login => [200]` and the page URL becoming the original destination. The form silently resetting = the click landed before the form was ready; refill and click again.
5. A captcha or email-verification wall = stop and tell the user. Do not attempt to bypass.

The session lives inside the `--rm` container: login survives within one Claude session and dies with it. If the user wants persistence, add a named volume and `--user-data-dir` to the registration (verify the mounted path is writable by the container user before relying on it). `--storage-state` is not the shortcut it looks like: it only applies to `--isolated` sessions, where it is a read-only seed rather than a save target.

## Step 3: Extracting content from old.reddit

Accessibility snapshots of reddit pages are huge; prefer `browser_evaluate`:

- Search results: `div.search-result-link`, title link `a.search-title`, meta `.search-result-meta`, comments link `a.search-comments`.
- Thread: post body `#siteTable .usertext-body`; comments `.commentarea .comment` with score `.score.unvoted` and body `.usertext-body`. Slice and trim inside the page function, not in context.

## Boundaries

- UA override and account login through the normal form: fine.
- Captcha solving, stealth/fingerprint-evasion libraries, scraping at volume: out of scope, refuse and explain.
