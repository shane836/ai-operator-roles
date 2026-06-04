# AI Operator Roles

A small, clean dataset of **41 "operator" roles at AI startups** — Chief of Staff, Founders Associate, Business Operations, Strategy & Ops, and Head/VP of Operations jobs — scraped from company job boards, normalized, and tagged.

The point of this repo is simple: **clone it, point your AI coding agent (Claude Code, Cursor, etc.) at the SQLite database, and ask questions** to understand what the AI-operator job market actually looks like right now — who's hiring, for what, at what comp, and what they expect you to do.

> Snapshot date: **June 2026**. This is a point-in-time scrape, not a live feed. Some postings are now closed.

---

## TL;DR for your AI agent

If you just landed here from a shared link, paste something like this to your agent:

> *"Read `README.md`, then open `ai_operator_roles.sqlite` and tell me what kinds of AI operator roles are out there. Group them by role family and seniority, show the comp ranges, and summarize what these jobs actually do day-to-day."*

Everything the agent needs to answer that is in the database. The schema and example queries are below.

---

## What's in here

| File | What it is |
|------|------------|
| `ai_operator_roles.sqlite` | **The dataset.** A SQLite database, 4 tables. This is the thing to query. |
| `roles_raw.json` | Raw scraped job postings (source of truth before normalization). |
| `tag_input.json` / `tag_results.json` | Input + output of the LLM tagging pass that assigned themes to each bullet. |
| `tag_workflow.js` | The tagging workflow script. |
| `build_db.py` | Rebuilds the `.sqlite` from the JSON files. |

You only need `ai_operator_roles.sqlite` to explore the data. The rest is provenance / reproducibility.

---

## The data at a glance

- **41 roles** across **41 companies** (EliseAI, Skydio, Ambience Healthcare, Handshake, SandboxAQ, Legora, Tavus, Inworld, micro1, and more).
- **Role families:** Chief of Staff (11), Founders Associate (7), Business Operations (7), Strategy & Ops (6), Head/VP of Operations (6).
- **Industries:** Healthcare/Bio AI, Fintech, AI Infrastructure, Legal Tech, Hardware/Robotics, EdTech, and others.
- **Seniority:** mostly Founding/Early IC and Chief-of-Staff level, ranging up to Head/VP and Director.
- **Comp:** disclosed salaries range **$55k–$366k**; ~half the postings don't disclose. Most disclosed roles land in the **$150k–$250k+** bands.
- **Location:** skews onsite in SF and NYC, with a meaningful remote/hybrid minority.

---

## Database schema

One row per posting in `roles`, with child tables for the bullet-point sections. Each responsibility and qualification bullet is tagged with a **theme** by an LLM pass, so you can slice the data by *what the work actually is* rather than just job title.

### `roles` — one row per job posting
| Column | Notes |
|--------|-------|
| `role_id` | Primary key |
| `url`, `company`, `title_raw` | Source posting |
| `role_family` | Chief of Staff / Founders Associate / Business Operations / Strategy & Ops / Head/VP of Operations / Specialist Ops |
| `industry_raw`, `industry_category` | e.g. "Healthcare/Bio AI", "Fintech", "AI Infrastructure" |
| `location_raw`, `location_city`, `remote_mode` | `remote_mode` ∈ Onsite / Remote / Hybrid / Unspecified |
| `seniority` | IC / Lead / Manager / Director / Head/VP / Chief of Staff / Founding-Early IC |
| `employment_type` | Full-time, etc. |
| `years_exp_raw`, `years_exp_min`, `years_exp_max` | Parsed experience requirements |
| `salary_raw`, `salary_min`, `salary_max`, `currency`, `pay_period` | Parsed comp |
| `comp_band` | Bucketed: `<100k`, `100-150k`, `150-200k`, `200-250k`, `250k+`, `Undisclosed` |
| `has_equity`, `has_bonus` | Boolean flags (1/0) |
| `ats` | Applicant tracking system the posting came from (ashby, greenhouse, etc.) |
| `fetch_status` | Scrape quality: `ok`, `partial`, `empty`, `blocked` — filter on `ok` for clean rows |
| `n_responsibilities`, `n_required`, `n_preferred`, `n_benefits` | Counts of child rows |

### `role_responsibilities` — one row per responsibility bullet
`role_id` → `roles`, plus `item_order`, `text`, and `theme`
(themes: Process/Systems, Cross-functional Execution, Strategy/Analytics, Finance/Ops, GTM/Customer, Founder/Exec Support, Hiring/People)

### `role_qualifications` — one row per qualification bullet
`role_id` → `roles`, plus `kind` (`required` | `preferred`), `item_order`, `text`, and `theme`
(themes: Soft Skills, Experience/Years, Domain Knowledge, Technical/AI Tooling, Location/Visa, Education)

### `role_benefits` — one row per perk
`role_id` → `roles`, plus `item_order`, `text`

---

## Quick start

No setup needed — `sqlite3` ships with macOS and most Linux distros.

```bash
git clone https://github.com/shane836/ai-operator-roles.git
cd ai-operator-roles

# Poke around interactively
sqlite3 ai_operator_roles.sqlite

# Or one-off queries
sqlite3 ai_operator_roles.sqlite "SELECT company, title_raw, comp_band FROM roles WHERE fetch_status='ok';"
```

### Example queries

```sql
-- The landscape: roles by family and seniority
SELECT role_family, seniority, COUNT(*) AS n
FROM roles GROUP BY role_family, seniority ORDER BY n DESC;

-- Where's the money? Disclosed comp by role family
SELECT role_family,
       MIN(salary_min) AS low, MAX(salary_max) AS high, COUNT(*) AS n
FROM roles WHERE salary_min IS NOT NULL
GROUP BY role_family ORDER BY high DESC;

-- What does a Chief of Staff actually DO? (responsibilities by theme)
SELECT r.theme, COUNT(*) AS n
FROM role_responsibilities r JOIN roles ro ON ro.role_id = r.role_id
WHERE ro.role_family = 'Chief of Staff'
GROUP BY r.theme ORDER BY n DESC;

-- What do they require vs. prefer? (qualification themes by kind)
SELECT kind, theme, COUNT(*) AS n
FROM role_qualifications GROUP BY kind, theme ORDER BY n DESC;

-- Remote-friendly roles with disclosed comp
SELECT company, title_raw, salary_min, salary_max
FROM roles WHERE remote_mode='Remote' AND salary_min IS NOT NULL
ORDER BY salary_max DESC;
```

---

## Good questions to ask your AI agent

Once it has the database open, these get interesting answers fast:

- *"What's the difference between a 'Chief of Staff' and a 'Founders Associate' role in this dataset, based on the actual responsibilities and qualifications?"*
- *"If I'm an early-career operator, which roles are realistically targetable, and what skills show up most often in their requirements?"*
- *"Which industries pay the most for operator roles, and is onsite vs. remote correlated with comp?"*
- *"Summarize the 'ideal candidate' for a founding operator role by aggregating the required qualifications across all of them."*
- *"Build me a profile of what AI startups want from their first operations hire."*

---

## How the dataset was built

1. **Scrape** job postings from company boards → `roles_raw.json`.
2. **Tag** each responsibility/qualification bullet with a theme via an LLM pass → `tag_results.json` (driver: `tag_workflow.js`).
3. **Normalize & load** into SQLite, deriving role family, comp bands, seniority, etc. → `build_db.py` writes `ai_operator_roles.sqlite`.

To rebuild the database from source:

```bash
python3 build_db.py
```

---

## Caveats

- **Point-in-time.** Captured June 2026; postings open and close constantly. Treat as a sample, not the whole market.
- **Imperfect parsing.** `role_family`, `seniority`, and comp bands are derived heuristically. A few rows have `fetch_status` of `partial`/`empty`/`blocked` — filter on `fetch_status='ok'` for the cleanest subset.
- **Comp is sparse.** Roughly half the postings don't disclose salary; aggregate comp figures only reflect those that do.
- **Small N.** 41 roles is enough to see patterns, not enough for statistical claims.
