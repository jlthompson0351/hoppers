# Project: hoppers

## What It Does
Automated hopper filling system with PLC integration. Controls weight-based filling operations, manages job targets via webhooks, and provides real-time dashboard with HDMI UI. Features webhook-driven PLC output for external system integration and persistent job state across restarts.

## Connects To
- Supabase (job status webhooks)
- OpenClaw (likely shares infrastructure)

## Tech Stack
- Language: Python
- Framework: Flask (API endpoints), OpenPLC (PLC control)
- Hardware: Raspberry Pi, PLC, weight sensors

## Current Status
- Phase: active
- Last updated: 2026-03-18
- Blockers: unknown

## Scope for Cursor
What Cursor should work on next:
- [ ] TBD

## Scope for OpenClaw
What OpenClaw manages:
- [ ] TBD

## Decisions Log
| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-18 | Deploy v3.4 with external webhook ingress | Live production with Tailscale Funnel |