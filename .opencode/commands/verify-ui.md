---
description: Verify the dashboard UI in a real browser against the host dev server
agent: build
---

Verify the dashboard UI end to end in a browser.

Load the `ui-verification` skill and run it against `http://127.0.0.1:8001/`.

Before starting, confirm the app is running (`make run`) and tell the user the
URL. If the local database is empty, ask whether to seed demo rows or run a
live refresh; do neither without approval.

Report findings with the skill's report format. Do not fix anything unless the
user asks.
