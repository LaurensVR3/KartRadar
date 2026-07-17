import datetime
import json


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return "pending — first check in progress"
    try:
        return datetime.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


def _dk(d: datetime.date) -> str:
    return f"{d.year}/{d.month}/{d.day}"


def render_home(rows: list[dict], days: list[datetime.date], last_checked: str | None) -> str:
    today = datetime.date.today()

    js_data = json.dumps(rows, ensure_ascii=False)
    date_meta = [
        {
            "key": _dk(d), "abbr": d.strftime("%a")[:2], "day": d.day, "mon": d.strftime("%b")[:3],
            "wknd": d.weekday() >= 5, "today": d == today,
        }
        for d in days
    ]
    js_dates = json.dumps(date_meta, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KartRadar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #EDEAE2;
    --surface: #F7F5EF;
    --surface-2: #F1EEE5;
    --ink: #1C1B19;
    --muted: #746F60;
    --amber: #B96A00;
    --amber-strong: #8F5300;
    --go: #1E7A42;
    --go-bg: #CBE7D2;
    --go-bg-hover: #B5DDBE;
    --stop-bg: #E7DFD8;
    --stop-ink: #8A5A4C;
    --line: #D9D3C3;
    --line-strong: #C6BFAC;
    --focus: #1F6FB2;
  }}

  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #16140F;
      --surface: #1E1B15;
      --surface-2: #24201A;
      --ink: #F1EEE4;
      --muted: #9C9584;
      --amber: #F2A63A;
      --amber-strong: #FFC670;
      --go: #3FBD73;
      --go-bg: #1E3B29;
      --go-bg-hover: #26492F;
      --stop-bg: #2B2521;
      --stop-ink: #C4877A;
      --line: #322D24;
      --line-strong: #433D30;
      --focus: #6BB6F2;
    }}
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html {{ background: var(--bg); }}

  body {{
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--ink);
    padding: 20px 20px 40px;
  }}

  a {{ color: inherit; }}

  ::selection {{ background: var(--amber); color: #fff; }}

  :focus-visible {{
    outline: 2px solid var(--focus);
    outline-offset: 2px;
  }}

  .wrap {{ max-width: 1400px; margin: 0 auto; }}

  /* ── Masthead ─────────────────────────────────────────────────────────── */

  .masthead {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 10px 24px;
    padding-bottom: 14px;
    margin-bottom: 8px;
    border-bottom: 2px solid var(--line-strong);
    position: relative;
  }}

  .masthead::after {{
    content: "";
    position: absolute;
    left: 0; bottom: -2px;
    height: 2px;
    width: 100%;
    background: var(--amber);
    transform-origin: left;
    animation: sweep-in 0.6s cubic-bezier(.2,.7,.3,1) 0.05s both;
  }}

  @keyframes sweep-in {{
    from {{ transform: scaleX(0); }}
    to   {{ transform: scaleX(1); }}
  }}

  .brand {{
    font-family: "Chakra Petch", "Inter", sans-serif;
    font-weight: 700;
    font-size: 1.65rem;
    letter-spacing: 0.01em;
    line-height: 1;
  }}
  .brand .accent {{ color: var(--amber); }}

  .tagline {{
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 4px;
    letter-spacing: 0.01em;
  }}

  .sweep-status {{
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: var(--ink);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--go);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--go) 20%, transparent);
    flex-shrink: 0;
  }}

  @media (prefers-reduced-motion: reduce) {{
    .masthead::after {{ animation: none; }}
  }}

  /* ── Toolbar ──────────────────────────────────────────────────────────── */

  .filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px 22px;
    align-items: flex-end;
    padding: 14px 16px;
    margin-bottom: 16px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
  }}
  .filter-group {{ display: flex; flex-direction: column; gap: 6px; }}
  .filter-label {{
    font-family: "JetBrains Mono", monospace;
    font-size: 0.66rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.09em;
  }}
  .pill-group {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .pill {{
    font-size: 0.76rem; font-weight: 500;
    padding: 4px 11px; border-radius: 99px; border: 1.5px solid var(--line-strong);
    background: var(--bg); color: var(--ink); cursor: pointer; user-select: none;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }}
  .pill:hover {{ border-color: var(--amber); color: var(--amber-strong); }}
  .pill.active {{ background: var(--ink); border-color: var(--ink); color: var(--surface); font-weight: 600; }}
  .pill.booking-private.active {{ background: var(--focus); border-color: var(--focus); color: #fff; }}
  .pill.booking-rental.active {{ background: var(--amber); border-color: var(--amber); color: #fff; }}
  .pill.toggle-pill.active {{ background: var(--go); border-color: var(--go); color: #fff; }}
  .pill.favorites-pill.active {{ background: var(--amber); border-color: var(--amber); color: #fff; }}
  #result-count {{
    font-family: "JetBrains Mono", monospace;
    font-size: 0.74rem; color: var(--muted); white-space: nowrap;
  }}
  #search-input {{
    font-family: "Inter", sans-serif;
    font-size: 0.78rem; padding: 5px 10px; border: 1.5px solid var(--line-strong);
    border-radius: 6px; background: var(--bg); color: var(--ink); width: 160px;
  }}
  #search-input:focus {{ border-color: var(--focus); }}

  /* ── Table ────────────────────────────────────────────────────────────── */

  .scroll-wrap {{
    overflow-x: auto;
    border: 1px solid var(--line);
    border-radius: 8px;
  }}
  table {{ border-collapse: collapse; background: var(--surface); white-space: nowrap; width: 100%; }}
  th, td {{
    border: 1px solid var(--line);
    text-align: center; font-size: 0.72rem; padding: 4px 2px; min-width: 34px;
  }}

  td.track-name {{
    text-align: left; padding: 7px 10px 7px 6px; min-width: 220px; white-space: normal;
    background: var(--surface); position: sticky; left: 0; z-index: 2; border-right: 2px solid var(--line-strong);
  }}
  .track-name-row {{ display: flex; align-items: flex-start; gap: 5px; }}
  .star-btn {{
    font-size: 1.05rem; line-height: 1.3; background: none; border: none; cursor: pointer;
    padding: 1px; color: var(--line-strong); flex-shrink: 0;
  }}
  .star-btn:hover {{ color: var(--amber); }}
  .star-btn.active {{ color: var(--amber); }}
  .track-name-body a {{
    display: block; font-weight: 600; font-size: 0.80rem; color: var(--ink); text-decoration: none;
  }}
  .track-name-body a:hover {{ color: var(--amber-strong); text-decoration: underline; }}
  .note {{ display: block; font-size: 0.66rem; color: var(--muted); margin-top: 1px; font-family: "JetBrains Mono", monospace; }}
  .badge {{
    display: inline-block; font-size: 0.58rem; padding: 1px 5px; border-radius: 3px; margin-top: 3px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
    font-family: "JetBrains Mono", monospace;
  }}
  .badge-country {{ background: var(--surface-2); color: var(--muted); border: 1px solid var(--line); }}
  .badge-session {{ background: var(--go-bg); color: var(--go); }}
  .badge-price {{ background: var(--surface-2); color: var(--amber-strong); border: 1px solid var(--line); }}

  th {{
    background: var(--surface-2); font-weight: 600; padding: 6px 2px; line-height: 1.35; vertical-align: bottom;
    font-family: "JetBrains Mono", monospace; color: var(--muted); font-size: 0.68rem;
  }}
  th:first-child {{
    text-align: left; padding-left: 10px; min-width: 220px; position: sticky; left: 0; z-index: 3;
    border-right: 2px solid var(--line-strong);
    font-family: "Inter", sans-serif; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.66rem;
  }}
  .mon {{ font-size: 0.6rem; color: var(--muted); opacity: 0.75; }}

  .wknd {{ background-color: var(--surface-2); }}
  th.wknd {{ background-color: var(--surface-2); }}
  .today-col {{ box-shadow: inset 0 0 0 2px var(--amber); }}
  th.today-col {{ background: var(--surface-2); color: var(--amber-strong); font-weight: 700; }}

  td.avail {{ background: var(--go-bg); cursor: pointer; padding: 0; position: relative; }}
  td.avail::after {{
    content: ""; position: absolute; inset: 2px; border-radius: 2px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
    pointer-events: none;
  }}
  td.avail a {{ display: block; width: 100%; height: 100%; min-height: 27px; }}
  td.avail:hover {{ background: var(--go-bg-hover); }}
  td.closed {{
    background: var(--stop-bg); color: var(--stop-ink); font-size: 0.6rem;
    overflow: hidden; text-overflow: ellipsis; max-width: 34px; font-family: "JetBrains Mono", monospace;
  }}
  td.unknown {{ color: var(--line-strong); background: var(--surface); font-family: "JetBrains Mono", monospace; }}
  tr.hidden {{ display: none; }}

  tr:nth-child(even) td.track-name {{ background: var(--surface-2); }}

  .footnote {{
    font-size: 0.7rem; color: var(--muted); margin-top: 14px; line-height: 1.5;
  }}

  .footer-links {{
    font-family: "JetBrains Mono", monospace;
    font-size: 0.7rem; color: var(--muted); margin-top: 6px; line-height: 1.5;
  }}
  .footer-links a {{ color: var(--muted); text-decoration: underline; text-decoration-color: var(--line-strong); }}
  .footer-links a:hover {{ color: var(--amber-strong); text-decoration-color: var(--amber-strong); }}
</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <div>
    <div class="brand">Kart<span class="accent">Radar</span></div>
    <div class="tagline">Karting availability — own-kart and rental — scanned across every venue we can reach</div>
  </div>
  <div class="sweep-status">
    <span class="dot" aria-hidden="true"></span>
    <span>{len(rows)} tracks checked · last check {_fmt_ts(last_checked)}</span>
  </div>
</header>

<div class="filters">
  <div class="filter-group"><span class="filter-label">Country</span><div class="pill-group" id="country-pills"></div></div>
  <div class="filter-group"><span class="filter-label">Booking type</span><div class="pill-group" id="booking-pills"></div></div>
  <div class="filter-group"><span class="filter-label" id="session-filter-label">Session class</span><div class="pill-group" id="session-pills"></div></div>
  <div class="filter-group"><span class="filter-label">Search</span><input type="text" id="search-input" placeholder="Track name…"></div>
  <div class="filter-group">
    <span class="filter-label">Options</span>
    <div class="pill-group">
      <span class="pill toggle-pill" id="bookable-only-pill">Bookable only</span>
      <span class="pill toggle-pill favorites-pill" id="favorites-only-pill">★ Favorites only</span>
    </div>
  </div>
  <span id="result-count"></span>
</div>

<div class="scroll-wrap">
<table id="avail-table">
  <thead id="avail-head"></thead>
  <tbody id="avail-body"></tbody>
</table>
</div>

<p class="footnote">★ Favorites and filters are saved in your browser only — no cookies, no tracking, nothing sent to a server.</p>
<p class="footer-links">
  <a href="https://github.com/LaurensVR3/KartRadar" target="_blank">Source on GitHub</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/LaurensVR3/OpenLap" target="_blank">My other AI slop</a>
</p>

</div>

<script>
const DATA  = {js_data};
const DATES = {js_dates};
const STORAGE_KEY = "kartradar:prefs";

const SESSION_LABELS = {{
  mini: "Mini / Rookie", junior: "Junior", "4stroke": "4-stroke", senior: "Senior",
  master: "Master", shifter: "Shifter / KZ / DD2", adult: "Adult", kids: "Kids / Family",
  drift: "Drift", biplace: "2-seater", endurance: "Endurance", general: "General",
}};
const BOOKING_LABELS = {{ private: "Own kart", rental: "Rental" }};

// ── Preferences: plain localStorage, purely client-side (no cookies, no
// server round-trip, no consent banner needed) ──────────────────────────────
function loadPrefs() {{
  let stored = null;
  try {{ stored = JSON.parse(localStorage.getItem(STORAGE_KEY)); }} catch (e) {{ stored = null; }}
  const defaults = {{
    favorites: [],
    countries: null, booking: null, sessions: null,
    search: "", bookableOnly: false, favoritesOnly: false,
  }};
  return Object.assign(defaults, stored || {{}});
}}

const prefs = loadPrefs();
let favorites = new Set(prefs.favorites);
let activeCountries = prefs.countries ? new Set(prefs.countries) : null;
let activeBooking   = prefs.booking   || null;   // single value — own-kart / rental are mutually exclusive
let activeSessions  = prefs.sessions  ? new Set(prefs.sessions)  : null;
let bookableOnly    = !!prefs.bookableOnly;
let favoritesOnly   = !!prefs.favoritesOnly;

function savePrefs() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify({{
    favorites: [...favorites],
    countries: activeCountries ? [...activeCountries] : null,
    booking: activeBooking,
    sessions: activeSessions ? [...activeSessions] : null,
    search: document.getElementById("search-input").value,
    bookableOnly, favoritesOnly,
  }}));
}}

const countrySet = [...new Set(DATA.map(r => r.country))].sort();
const sessionSet = [...new Set(DATA.flatMap(r => r.sessions))].sort();
const bookingSet = [...new Set(DATA.map(r => r.booking))].sort();

// Competitive racing classes (mini/junior/senior/master/shifter/4stroke) only
// ever show up on "Own kart" rows; rental age-tiers (adult/kids) and kart
// formats (drift/biplace/endurance) only ever show up on "Rental" rows — real
// data confirms an almost total split. They're two different questions
// ("which racing class" vs. "what kind of rental") that don't compare to each
// other, so show only the relevant one once a booking type is picked instead
// of one flat list mixing both.
const sessionsByBooking = {{}};
bookingSet.forEach(b => {{
  sessionsByBooking[b] = [...new Set(DATA.filter(r => r.booking === b).flatMap(r => r.sessions))].sort();
}});
const SESSION_FILTER_LABELS = {{ private: "Racing class", rental: "Rental type" }};

function makePills(containerId, items, labelFn, extraClass, activeSetGetter, onToggle) {{
  const div = document.getElementById(containerId);
  items.forEach(val => {{
    const pill = document.createElement("span");
    pill.className = "pill" + (extraClass ? " " + extraClass(val) : "");
    pill.textContent = labelFn(val);
    pill.dataset.value = val;
    if (activeSetGetter() && activeSetGetter().has(val)) pill.classList.add("active");
    pill.addEventListener("click", () => onToggle(val, pill));
    div.appendChild(pill);
  }});
}}

function togglePill(val, pill, activeSet, setFn) {{
  if (activeSet === null) {{
    setFn(new Set([val]));
    pill.classList.add("active");
    pill.parentElement.querySelectorAll(".pill").forEach(p => {{ if (p !== pill) p.classList.remove("active"); }});
  }} else if (activeSet.has(val)) {{
    activeSet.delete(val);
    pill.classList.remove("active");
    if (activeSet.size === 0) {{
      setFn(null);
      pill.parentElement.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
    }} else {{ setFn(activeSet); }}
  }} else {{
    activeSet.add(val);
    pill.classList.add("active");
    setFn(activeSet);
  }}
  savePrefs();
  applyFilter();
}}

function renderSessionPills() {{
  document.getElementById("session-pills").innerHTML = "";
  const items = activeBooking ? sessionsByBooking[activeBooking] : sessionSet;
  makePills("session-pills", items, s => SESSION_LABELS[s] || s, null,
    () => activeSessions, (val, pill) => togglePill(val, pill, activeSessions, s => activeSessions = s));
}}

function updateSessionFilterLabel() {{
  document.getElementById("session-filter-label").textContent =
    SESSION_FILTER_LABELS[activeBooking] || "Session class";
}}

function makeExclusivePills(containerId, items, labelFn, extraClass, activeGetter, onSelect) {{
  const div = document.getElementById(containerId);
  items.forEach(val => {{
    const pill = document.createElement("span");
    pill.className = "pill" + (extraClass ? " " + extraClass(val) : "");
    pill.textContent = labelFn(val);
    pill.dataset.value = val;
    if (activeGetter() === val) pill.classList.add("active");
    pill.addEventListener("click", () => onSelect(val, pill));
    div.appendChild(pill);
  }});
}}

function toggleExclusivePill(val, pill, currentVal, setFn) {{
  const group = pill.parentElement;
  group.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
  if (currentVal === val) {{
    setFn(null);   // clicking the already-active pill clears it -> show all
  }} else {{
    setFn(val);
    pill.classList.add("active");
  }}
  // A session-class filter picked while looking at Rental doesn't necessarily
  // apply to Own kart (or vice versa) — start fresh and rebuild the pill list
  // to the set that's actually relevant to the newly selected booking type,
  // rather than showing e.g. "Senior" as an option while browsing Rental.
  activeSessions = null;
  renderSessionPills();
  updateSessionFilterLabel();
  savePrefs();
  applyFilter();
}}

makePills("country-pills", countrySet, c => c === "??" ? "?? (unknown)" : c, null,
  () => activeCountries, (val, pill) => togglePill(val, pill, activeCountries, s => activeCountries = s));
makeExclusivePills("booking-pills", bookingSet, b => BOOKING_LABELS[b] || b, val => "booking-" + val,
  () => activeBooking, (val, pill) => toggleExclusivePill(val, pill, activeBooking, v => activeBooking = v));
renderSessionPills();
updateSessionFilterLabel();

const searchInput = document.getElementById("search-input");
searchInput.value = prefs.search || "";
searchInput.addEventListener("input", () => {{ savePrefs(); applyFilter(); }});

const bookableOnlyPill = document.getElementById("bookable-only-pill");
bookableOnlyPill.classList.toggle("active", bookableOnly);
bookableOnlyPill.addEventListener("click", function() {{
  bookableOnly = !bookableOnly;
  this.classList.toggle("active", bookableOnly);
  savePrefs();
  applyFilter();
}});

const favoritesOnlyPill = document.getElementById("favorites-only-pill");
favoritesOnlyPill.classList.toggle("active", favoritesOnly);
favoritesOnlyPill.addEventListener("click", function() {{
  favoritesOnly = !favoritesOnly;
  this.classList.toggle("active", favoritesOnly);
  savePrefs();
  applyFilter();
}});

// ── Table ────────────────────────────────────────────────────────────────────

const head = document.getElementById("avail-head");
const hrow = document.createElement("tr");
const th0 = document.createElement("th");
th0.textContent = "Track";
hrow.appendChild(th0);
DATES.forEach(dm => {{
  const th = document.createElement("th");
  th.className = (dm.wknd ? "wknd " : "") + (dm.today ? "today-col" : "");
  th.title = dm.key;
  th.innerHTML = `${{dm.abbr}}<br>${{dm.day}}<br><span class="mon">${{dm.mon}}</span>`;
  hrow.appendChild(th);
}});
head.appendChild(hrow);

const rowsById = Object.fromEntries(DATA.map(r => [r.id, r]));

// A row's price/duration isn't one number — RACB Spa's Senior class alone is
// €32 (half day) or €50 (full day); Genk's price depends entirely on which
// class you pick (€52 Mini vs. €72-82 Senior). Show a range across whatever's
// currently in view, narrowing to the exact figure once the session filter
// picks out a single class — recomputed on every filter change, not fixed at
// page load.
function formatPriceDuration(row) {{
  const table = row.price_table || [];
  const relevant = (activeSessions && table.some(e => activeSessions.has(e.session)))
    ? table.filter(e => activeSessions.has(e.session))
    : table;
  const fmtRange = (vals, decimals) => {{
    if (vals.length === 0) return "";
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const f = v => decimals ? String(Math.round(v * 10) / 10) : v.toFixed(0);
    return lo === hi ? f(lo) : `${{f(lo)}}–${{f(hi)}}`;
  }};
  const prices = relevant.map(e => e.price).filter(p => p !== null && p !== undefined && p > 0);
  const durs   = relevant.map(e => e.dur_h).filter(d => d !== null && d !== undefined && d > 0);
  const priceRange = fmtRange(prices, false);
  const durRange = fmtRange(durs, true);
  return {{
    priceStr: priceRange ? `€${{priceRange}}` : "",
    durStr: durRange ? `${{durRange}}h` : "",
  }};
}}

function updateRowPriceDisplay(tr) {{
  const {{ priceStr, durStr }} = formatPriceDuration(rowsById[tr.dataset.id]);
  const durEl = tr.querySelector(".dur-note");
  const priceEl = tr.querySelector(".badge-price");
  durEl.textContent = durStr;
  durEl.style.display = durStr ? "" : "none";
  priceEl.textContent = priceStr;
  priceEl.style.display = priceStr ? "" : "none";
}}

const tbody = document.getElementById("avail-body");
DATA.forEach(row => {{
  const tr = document.createElement("tr");
  tr.dataset.id = row.id;
  tr.dataset.country = row.country;
  tr.dataset.booking = row.booking;
  tr.dataset.sessions = JSON.stringify(row.sessions);
  tr.dataset.name = row.name.toLowerCase();

  const td0 = document.createElement("td");
  td0.className = "track-name";
  const sessionBadges = row.sessions.map(s => `<span class="badge badge-session">${{SESSION_LABELS[s] || s}}</span>`).join(" ");
  td0.innerHTML = `
    <div class="track-name-row">
      <button class="star-btn${{favorites.has(row.id) ? " active" : ""}}" data-id="${{row.id}}" title="Toggle favorite">${{favorites.has(row.id) ? "★" : "☆"}}</button>
      <div class="track-name-body">
        <a href="${{row.booking_url}}" target="_blank">${{row.name}}</a>
        ${{row.note ? `<span class="note">${{row.note}}</span>` : ""}}
        <span class="note dur-note"></span>
        <span>
          <span class="badge badge-country">${{row.country}}</span>
          ${{sessionBadges}}
          <span class="badge badge-price"></span>
        </span>
      </div>
    </div>`;
  td0.querySelector(".star-btn").addEventListener("click", () => {{
    if (favorites.has(row.id)) favorites.delete(row.id); else favorites.add(row.id);
    const btn = td0.querySelector(".star-btn");
    btn.classList.toggle("active", favorites.has(row.id));
    btn.textContent = favorites.has(row.id) ? "★" : "☆";
    savePrefs();
    applyFilter();
  }});
  tr.appendChild(td0);
  updateRowPriceDisplay(tr);

  DATES.forEach(dm => {{
    const td = document.createElement("td");
    const info = (row.availability || {{}})[dm.key];
    const base = (dm.wknd ? "wknd " : "") + (dm.today ? "today-col" : "");
    if (info === undefined || info === null) {{
      td.className = "unknown " + base;
      td.textContent = "–";
    }} else if (info.available) {{
      td.className = "avail " + base;
      td.title = info.label || "";
      const a = document.createElement("a");
      a.href = row.booking_url; a.target = "_blank";
      td.appendChild(a);
    }} else {{
      td.className = "closed " + base;
      td.title = info.label || "";
      td.textContent = (info.label && info.label.length <= 9) ? info.label : "";
    }}
    tr.appendChild(td);
  }});

  tbody.appendChild(tr);
}});

function rowHasAvailability(tr) {{ return tr.querySelectorAll("td.avail").length > 0; }}

function applyFilter() {{
  const search = searchInput.value.toLowerCase().trim();
  let visible = 0;
  document.querySelectorAll("#avail-body tr").forEach(tr => {{
    const rowSessions = JSON.parse(tr.dataset.sessions);
    const ok =
      (activeCountries === null || activeCountries.has(tr.dataset.country)) &&
      (activeBooking === null || tr.dataset.booking === activeBooking) &&
      (activeSessions === null || rowSessions.some(s => activeSessions.has(s))) &&
      (!search || tr.dataset.name.includes(search)) &&
      (!bookableOnly || rowHasAvailability(tr)) &&
      (!favoritesOnly || favorites.has(tr.dataset.id));
    tr.classList.toggle("hidden", !ok);
    if (ok) visible++;
    updateRowPriceDisplay(tr);
  }});
  document.getElementById("result-count").textContent = `${{visible}} track${{visible !== 1 ? "s" : ""}}`;
}}

applyFilter();
</script>
</body>
</html>"""
