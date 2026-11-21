# Source Research

Use this folder for candidate-source research written by the `source-researcher`
subagent or by hand.

Each file should answer:

- Is the source public, and is scraping allowed by `robots.txt` and the terms?
- What are the listing and detail URL patterns?
- Which fields are available (title, company, location, posted date, salary,
  remote, employment type, description, Japanese level, visa sponsorship)?
- Is there a public API, RSS/Atom feed, JSON-LD, or embedded JSON?
- Is a login, headless browser, or special auth required?
- What are the risks and the verdict (implement / defer / reject)?

After a source is adopted, add a short summary to `docs/sources.md` and keep the
detailed evidence in this folder.

Current launch sources are documented directly in `docs/sources.md`; this folder
is for future candidates.
