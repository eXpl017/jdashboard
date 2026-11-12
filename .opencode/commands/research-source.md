---
description: Research a candidate job source for the dashboard and write a source brief (no code changes)
agent: build
---

Research a candidate job source for the Japan cybersecurity jobs dashboard and
write a brief. Do not write application code.

Source to research: $ARGUMENTS

Load the `source-onboarding` skill and run its research phase only.

1. Delegate to the `source-researcher` subagent. It writes
   `docs/research/<source>.md` with:
   - the verdict (`implement` / `defer` / `reject`) and one-sentence reason,
   - listing and detail URL patterns plus pagination,
   - the `robots.txt` result for the exact paths involved, with evidence,
   - which fields exist (title, company, location, posted date, salary, remote,
     employment type, description, Japanese level, visa sponsorship),
   - anti-bot/login findings, expected volume, and risks.
2. Report the verdict and the key evidence back to the user.
3. If the verdict is `implement`, say so and point at `/add-source <source>` to
   continue with the implementation.

Hard rules: no login/CAPTCHA/Cloudflare bypass, no fetching apply/login/member
pages, keep evidence short, and never paste full HTML into the brief.
