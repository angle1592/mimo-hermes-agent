# ClawEmail (网易) — Potential Hermes Email Platform

## Overview

claw.163.com — NetEase's email service for AI Agents. Each agent gets a `@claw.163.com` address.

## Status (2026-05)

Internal testing (内测). Sign up at `claw.163.com/projects/dashboard/`.

## Two Modes

| Mode | What | Use Case |
|------|------|----------|
| **Email Channel** | OpenClaw plugin — agent reads/responds to emails | Smart customer service |
| **mail-cli** | CLI tool for email ops | Script-based batch processing |

## CLI Example

```bash
mail-cli compose send --to "a@b.com" --subject "Report" --body "See attached" --attach data.csv
```

## Skills Available

github-triage, daily-report, support-router, notify-hub (+ freelance-inbox, event-signup coming)

## Relevance to Hermes

Could serve as a Hermes gateway platform adapter — agent gets a `@claw.163.com` address, receives tasks via email, sends results as replies. Similar role to DingTalk/WeChat adapters but email-based. Worth investigating when it exits internal testing.

## Docs

- Product: `claw.163.com`
- Docs: `claw.163.com/projects/doc/`
