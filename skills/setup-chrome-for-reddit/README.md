# setup-chrome-for-reddit

Gets the Playwright MCP browser through Reddit's bot detection, and logs it in when the task needs an account.

Reddit answers the stock Playwright headless browser with 403 and "You've been blocked by network security" on the first document request — server-side detection of the `HeadlessChrome` user-agent token, before any JavaScript runs. The same address with a normal desktop user-agent gets 200. Logged-out Reddit is close to useless anyway: unauthenticated `.json` endpoints return an HTML shell rather than JSON, and search redirects to the login form.

## What the skill does

- **Fixes the MCP registration** — re-registers the `playwright` server with a `--user-agent` that carries no `Headless` token. That alone is enough; no stealth plugins.
- **Drives the login** — navigates the normal `old.reddit.com` form, dismisses the cookie dialog, submits, and verifies the result from the network log instead of guessing from the rendered page. Credentials come from the user at run time and are never written anywhere.
- **Extracts content cheaply** — accessibility snapshots of Reddit pages are enormous, so it reads threads and search results through `browser_evaluate` with the `old.reddit` selectors, slicing inside the page function.

## Boundaries

The user-agent override and a normal account login are in scope. Captcha solving, fingerprint-evasion libraries, and scraping at volume are not — the skill refuses and says why. A captcha or email-verification wall is a hard stop that goes back to the user.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install setup-chrome-for-reddit@claude-code-companions
```

Requires Docker (the skill registers the MCP server as a container) and the `WebSearch` tool for finding thread URLs, since most search engines block the headless browser outright.
