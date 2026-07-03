---
name: hermes-tweet
description: Use Hermes Tweet with Hermes Agent for X/Twitter research, monitoring, and approval-gated action planning.
argument-hint: "[goal or task]"
---

Use Hermes Tweet when a user asks Hermes Agent to research X/Twitter, monitor public social context, prepare tweet-related analysis, or plan actions that must stay behind explicit approval.

## Source

Hermes Tweet lives at https://github.com/Xquik-dev/hermes-tweet and installs as a Hermes Agent plugin. Use that repository as the implementation source, documentation source, and issue tracker.

## Capability Map

- `tweet_explore`: use first for ungated planning, capability discovery, and no-network exploration.
- `tweet_read`: use for read-only X/Twitter lookup when `XQUIK_API_KEY` is configured.
- `tweet_action`: use only when actions are explicitly enabled with `HERMES_TWEET_ENABLE_ACTIONS=true` and the user asked for the action.

## Workflow

1. Start with `tweet_explore` to confirm the task shape and available routes.
2. Use `tweet_read` for public X/Twitter lookup, monitoring context, and evidence gathering.
3. Use `tweet_action` only after the user gives explicit action approval and the environment enables actions.
4. Summarize findings with links, timestamps, and clear uncertainty when source data is incomplete.

## Safety

- Do not ask users to paste credentials, cookies, or session material into chat.
- Treat `XQUIK_API_KEY` as an environment variable only.
- Keep write actions opt-in, explicit, and reversible when possible.
- Summarize external posts instead of copying long text.
- Refuse requests that would bypass platform rules, impersonate someone, or automate spam.
