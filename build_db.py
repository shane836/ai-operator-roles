#!/usr/bin/env python3
"""Build ai_operator_roles.sqlite from scraped roles + LLM theme tags.

Schema (approved):
  roles                 — one row per posting (41 rows, degraded ones flagged)
  role_responsibilities — one row per responsibility bullet (+ theme)
  role_qualifications   — one row per qualification bullet, kind=required|preferred (+ theme)
  role_benefits         — one row per perk
"""
import json, os, re, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "ai_operator_roles.sqlite")
roles = json.load(open(os.path.join(HERE, "roles_raw.json")))
tags = {t["url"]: t for t in json.load(open(os.path.join(HERE, "tag_results.json")))}

# ---------- categorical derivations ----------

def role_family(title):
    t = (title or "").lower()
    if not t:
        return None
    if "chief of staff" in t:
        return "Chief of Staff"
    if "found" in t and any(k in t for k in ("associate", "operator", "ops", "operation")):
        return "Founders Associate"
    if any(k in t for k in ("head of", "vp of", "vp ", "v.p", "director", "gm,", "gm ", "general manager")):
        return "Head/VP of Operations"
    if "strateg" in t:
        return "Strategy & Ops"
    if any(k in t for k in ("business operation", "business ops", "operations", "ops ", " ops", "operator")):
        return "Business Operations"
    return "Specialist Ops"

def industry_category(raw):
    t = (raw or "").lower()
    if not t:
        return None
    if any(k in t for k in ("health", "clinical", "care", "bio", "molecular", "patient", "medic")):
        return "Healthcare/Bio AI"
    if any(k in t for k in ("legal", "law ", "lawyer", "litigation")):
        return "Legal Tech"
    if any(k in t for k in ("fintech", "payment", "finance", "financial", "banking", "tax", "accounting")):
        return "Fintech"
    if any(k in t for k in ("housing", "real estate", "proptech", "property", "rent", "dwell")):
        return "PropTech/RealEstate"
    if any(k in t for k in ("education", "edtech", "teaching", "teacher", "student", "learning")):
        return "EdTech"
    if any(k in t for k in ("hardware", "robot", "drone", "device", "simulation", "aerospace")):
        return "Hardware/Robotics"
    if any(k in t for k in ("energy", "industrial", "manufactur", "nuclear", "grid")):
        return "Industrial/Energy"
    if any(k in t for k in ("federal", "govern", "defense", "public sector")):
        return "Other/GovTech"
    if any(k in t for k in ("sales", "gtm", "go-to-market", "marketing", "revenue", "growth")):
        return "GTM/Sales AI"
    if any(k in t for k in ("infrastructure", "training data", "model", "llm", "developer", "platform", "agent", "ai ")):
        return "AI Infrastructure"
    return "Other/GovTech"

def seniority_bucket(raw, title):
    t = (raw or "").lower() + " " + (title or "").lower()
    if any(k in t for k in ("founding", "early")):
        return "Founding/Early IC"
    if "chief of staff" in t:
        return "Chief of Staff"
    if any(k in t for k in ("vp", "v.p", "head of", "head,", "head ")):
        return "Head/VP"
    if "director" in t:
        return "Director"
    if "lead" in t:
        return "Lead"
    if "manager" in t:
        return "Manager"
    if any(k in t for k in ("ic", "individual contributor")):
        return "IC"
    return "IC"

def remote_mode(raw):
    t = (raw or "").lower()
    if not t:
        return "Unspecified"
    if "hybrid" in t:
        return "Hybrid"
    if "remote" in t:
        return "Remote"
    if any(k in t for k in ("onsite", "on-site", "in person", "in-person", "in office", "in-office")):
        return "Onsite"
    return "Unspecified"

def comp_band(smin, smax):
    v = smax if smax else smin
    if not v:
        return "Undisclosed"
    if v < 100000:
        return "<100k"
    if v < 150000:
        return "100-150k"
    if v < 200000:
        return "150-200k"
    if v < 250000:
        return "200-250k"
    return "250k+"

def parse_years(raw):
    if not raw:
        return None, None
    nums = re.findall(r"\d+", raw)
    if not nums:
        return None, None
    nums = [int(n) for n in nums if int(n) < 60]
    if not nums:
        return None, None
    lo = min(nums)
    hi = max(nums) if len(nums) > 1 else (None if "+" in raw else min(nums))
    return lo, hi

def has_bonus(salary_raw):
    t = (salary_raw or "").lower()
    return 1 if any(k in t for k in ("bonus", "ote", "on-target", "on target", "commission")) else 0

# ---------- build ----------

if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
c = con.cursor()
c.executescript("""
CREATE TABLE roles (
  role_id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE,
  company TEXT,
  title_raw TEXT,
  role_family TEXT,
  industry_raw TEXT,
  industry_category TEXT,
  location_raw TEXT,
  location_city TEXT,
  remote_mode TEXT,
  seniority TEXT,
  employment_type TEXT,
  years_exp_raw TEXT,
  years_exp_min INTEGER,
  years_exp_max INTEGER,
  salary_raw TEXT,
  salary_min INTEGER,
  salary_max INTEGER,
  currency TEXT,
  pay_period TEXT,
  comp_band TEXT,
  has_equity INTEGER,
  has_bonus INTEGER,
  ats TEXT,
  fetch_status TEXT,
  n_responsibilities INTEGER,
  n_required INTEGER,
  n_preferred INTEGER,
  n_benefits INTEGER
);
CREATE TABLE role_responsibilities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role_id INTEGER REFERENCES roles(role_id),
  item_order INTEGER,
  text TEXT,
  theme TEXT
);
CREATE TABLE role_qualifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role_id INTEGER REFERENCES roles(role_id),
  kind TEXT,          -- 'required' | 'preferred'
  item_order INTEGER,
  text TEXT,
  theme TEXT
);
CREATE TABLE role_benefits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role_id INTEGER REFERENCES roles(role_id),
  item_order INTEGER,
  text TEXT
);
""")

def city_from(raw):
    if not raw:
        return None
    t = raw.lower()
    if "remote" in t and not any(c in t for c in ("new york", "san franc", "london")):
        return "Remote"
    for city in ["San Francisco", "New York", "London", "Los Angeles", "Boston", "Seattle",
                 "Austin", "Chicago", "Toronto", "Berlin", "Paris", "Bangalore", "Mountain View",
                 "Palo Alto", "EMEA", "Remote"]:
        if city.lower() in t:
            return city
    return raw.split(",")[0].strip()[:40]

for r in roles:
    url = r["url"]
    resp = r.get("responsibilities") or []
    req = r.get("required_qualifications") or []
    pref = r.get("preferred_qualifications") or []
    ben = r.get("benefits") or []
    smin, smax = r.get("salary_min"), r.get("salary_max")
    ylo, yhi = parse_years(r.get("years_experience"))
    eq = r.get("equity_mentioned")
    fetch = r.get("fetch_status")
    has_eq = (1 if eq else 0) if fetch == "ok" or eq is not None else None
    c.execute("""INSERT INTO roles (url,company,title_raw,role_family,industry_raw,industry_category,
        location_raw,location_city,remote_mode,seniority,employment_type,years_exp_raw,years_exp_min,
        years_exp_max,salary_raw,salary_min,salary_max,currency,pay_period,comp_band,has_equity,has_bonus,
        ats,fetch_status,n_responsibilities,n_required,n_preferred,n_benefits)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        url, r.get("company_name"), r.get("role_title"), role_family(r.get("role_title")),
        r.get("company_industry"), industry_category(r.get("company_industry")),
        r.get("location"), city_from(r.get("location")), remote_mode(r.get("remote_policy")),
        seniority_bucket(r.get("seniority_level"), r.get("role_title")),
        (r.get("employment_type") or "").lower().replace("full-time", "full-time").strip() or None,
        r.get("years_experience"), ylo, yhi,
        r.get("salary_raw"), smin, smax, r.get("salary_currency"),
        r.get("salary_period"), comp_band(smin, smax),
        has_eq, has_bonus(r.get("salary_raw")),
        r.get("ats_platform"), fetch,
        len(resp), len(req), len(pref), len(ben)))
    rid = c.lastrowid
    tg = tags.get(url, {})
    rt = tg.get("responsibilities_themes") or []
    qt = tg.get("required_themes") or []
    pt = tg.get("preferred_themes") or []
    for i, txt in enumerate(resp):
        c.execute("INSERT INTO role_responsibilities (role_id,item_order,text,theme) VALUES (?,?,?,?)",
                  (rid, i + 1, txt, rt[i] if i < len(rt) else None))
    for i, txt in enumerate(req):
        c.execute("INSERT INTO role_qualifications (role_id,kind,item_order,text,theme) VALUES (?,?,?,?,?)",
                  (rid, "required", i + 1, txt, qt[i] if i < len(qt) else None))
    for i, txt in enumerate(pref):
        c.execute("INSERT INTO role_qualifications (role_id,kind,item_order,text,theme) VALUES (?,?,?,?,?)",
                  (rid, "preferred", i + 1, txt, pt[i] if i < len(pt) else None))
    for i, txt in enumerate(ben):
        c.execute("INSERT INTO role_benefits (role_id,item_order,text) VALUES (?,?,?)", (rid, i + 1, txt))

con.commit()
for tbl in ("roles", "role_responsibilities", "role_qualifications", "role_benefits"):
    n = c.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"{tbl:24} {n} rows")
con.close()
print("DB written:", DB)
