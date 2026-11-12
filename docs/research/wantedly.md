# Wantedly

## Verdict

defer — robots allows the paths and the pages are public, but listings are
rendered client-side from an internal Apollo GraphQL endpoint, so a stable
public data source has not been identified yet.

## Access

- Listing: `https://www.wantedly.com/projects` (canonicalizes to
  `https://www.wantedly.com/projects/list`; keyword search via
  `?search[keywords]=<term>`).
- Detail: `https://www.wantedly.com/projects/<id>` (project pages).
- Login required: no for listing and project pages. Login/member paths exist
  but are not needed for reading listings.
- Anti-bot: none observed. A plain HTTP client received `200` with normal
  content; no Cloudflare challenge, no 403.
- robots.txt: `https://www.wantedly.com/robots.txt` returns a
  `User-Agent: *` group. Disallowed paths are `/enterprise/`, `/users/*/edit`,
  `/users/edit`, `/stats`, `/users/en`, `/users/ja`, `/user/*` (auth),
  `/messages`, `/bookmarked_projects`, `/invitations`, `/profile_steps/`,
  `/inquiry/`, and a few `*_supplement*.js` endpoints.
  **Listing and detail paths (`/projects*`, `/users/<id>`) are not
  disallowed.**
- Terms notes: no explicit scraping or AI-crawler restriction was found on the
  public pages. The site is a business/professional network (Wantedly is a
  service of Infostandard), so listings are job posts written by companies
  rather than agency-normalized postings.

## Data available

| Field | Available? | Where |
| --- | --- | --- |
| title | yes | project title, in `__NEXT_DATA__`/GraphQL project object |
| company | yes | company name linked from each project |
| location | yes | project location (Japanese format) |
| posted date | unconfirmed | not present in the initial HTML payload; likely in the GraphQL project object |
| salary | unlikely | not observed in the list payload |
| remote | unconfirmed | remote work may appear as a project tag |
| employment type | yes | project tags (中途/新規/インターン) |
| description | yes | project body, Japanese |
| Japanese level | n/a | listings are Japanese-language |
| visa sponsorship | unconfirmed | would need a detail-page check |

## URL patterns

- List: `https://www.wantedly.com/projects/list`
- Keyword search: `https://www.wantedly.com/projects?search[keywords]=<urlencoded>`
- Project detail: `https://www.wantedly.com/projects/<project_id>`
- Company: `https://www.wantedly.com/users/<user_id>`

## Sample evidence

- `GET /robots.txt` → `200`, `User-Agent: *` group as listed above.
- `GET /projects?search[keywords]=セキュリティ` → `200`, `<title>中途・インターンの募集 | Wantedly</title>`.
- The response is a Next.js shell that embeds
  `<script id="__NEXT_DATA__" type="application/json">` containing an Apollo
  cache (`__apollo` → `ROOT_QUERY` → `currentEnvironment`), i.e. the project
  list is fetched client-side from a GraphQL endpoint.
- The fetched HTML contains skeleton placeholders (`LoadingPostItem__Skeleton*`)
  rather than project rows, and no `JobPosting` JSON-LD for the list page.
- Markers `posted_at`, `salary`, and `project_title` were absent from the
  initial HTML payload.

## Implementation notes

If this source is adopted later:

- The GraphQL endpoint behind `__NEXT_DATA__` would have to be identified and
  called directly, which means relying on an undocumented internal API.
  Treat that as fragile: verify the endpoint still exists before writing a
  scraper, and keep the request rate at the standard ~1 req/s.
- Alternatively, check whether a project detail page contains
  `JobPosting` JSON-LD; if it does, detail pages could be parsed directly and
  only the listing step would need the GraphQL call.
- Deduplicate on the canonical project URL.
- Listings are Japanese; the language classifier will mark them `ja`.
- Expect heavy overlap with the general Japanese job market and relatively few
  roles that classify as `engineering`/`operations` security roles.

## Risks

- Undocumented GraphQL API: the largest risk. A change there silently breaks
  the source, which is why the verdict is `defer`.
- Project-based hiring posts are written by companies and often lack salary,
  employment type, and structured dates.
- Mostly Japanese-language and startup-focused, so the yield of technical
  security roles may be low compared with Daijob.
- The listing page is large (hundreds of KB of inline CSS/JS); a scraper must
  not store it as a fixture verbatim.
