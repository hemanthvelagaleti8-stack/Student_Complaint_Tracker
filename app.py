"""Campus Complaint Tracker - self-contained local web application.

Run from the assignment folder:
    py 07_complaint_tracker/app.py
Then open http://127.0.0.1:8000 in your browser.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "data.json"

HOST = "0.0.0.0"
PORT = int(__import__("os").environ.get("PORT", "8000"))

CATEGORIES = ["Electrical", "Water", "Network", "Other"]
STATUSES = ["Pending", "In progress", "Resolved"]


def load_data():
    if not DATA_FILE.exists():
        return {"tickets": []}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("tickets"), list):
            raise ValueError("Invalid data structure")
        return data
    except (json.JSONDecodeError, ValueError):
        # Keep a damaged file safe rather than silently overwriting it.
        raise RuntimeError(f"Could not read {DATA_FILE}. Check that it contains valid JSON.")


def save_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(DATA_FILE)


def word_set(description):
    """Return lowercase words from a complaint description."""
    return set(re.findall(r"\w+", description.lower()))


def duplicates(candidate, tickets):
    """Find unresolved tickets in the same category/location with Jaccard >= 0.4."""
    candidate_words = word_set(candidate["description"])
    results = []
    for ticket in tickets:
        if ticket["status"] == "Resolved":
            continue
        if ticket["category"].casefold() != candidate["category"].casefold():
            continue
        if ticket["location"].casefold() != candidate["location"].casefold():
            continue
        other_words = word_set(ticket["description"])
        union = candidate_words | other_words
        score = len(candidate_words & other_words) / len(union) if union else 0
        if score >= 0.4:
            results.append((ticket, score))
    return results


def ticket_age(ticket):
    created = date.fromisoformat(ticket["created"])
    return max(0, (date.today() - created).days)


def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body, message="", error=False):
    banner = ""
    if message:
        css = "error" if error else "success"
        banner = f'<div class="notice {css}">{esc(message)}</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root{{--ink:#182230;--muted:#64748b;--line:#e2e8f0;--paper:#f5f7fb;--blue:#2457d6;--navy:#14213d;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Arial,sans-serif}}
header{{background:var(--navy);color:white;padding:24px max(20px,calc((100% - 1180px)/2))}}
header h1{{margin:0;font-size:25px}} header p{{margin:5px 0 0;color:#cbd5e1}}
main{{max-width:1180px;margin:24px auto;padding:0 16px 40px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}
.card{{background:white;border:1px solid var(--line);border-radius:13px;padding:19px;box-shadow:0 3px 12px #0f172a08}}
.wide{{grid-column:1/-1}} h2{{font-size:18px;margin:0 0 14px}} h3{{font-size:15px;margin:18px 0 8px}}
label{{display:block;font-weight:600;font-size:13px;margin:10px 0 5px}}
input,select,textarea{{width:100%;padding:10px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit;background:white}}
textarea{{min-height:82px;resize:vertical}} button,.button{{display:inline-block;border:0;border-radius:8px;background:var(--blue);color:white;padding:10px 15px;font-weight:700;cursor:pointer;text-decoration:none;margin-top:12px}}
button:hover,.button:hover{{filter:brightness(.93)}} .secondary{{background:#e8eefc;color:#1e40af}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{text-align:left;padding:10px 9px;border-bottom:1px solid var(--line);vertical-align:top}} th{{background:#f8fafc;color:#475569}}
.table-wrap{{overflow-x:auto}} .muted{{color:var(--muted)}} .notice{{padding:12px 14px;border-radius:9px;margin-bottom:16px}}
.success{{background:#e8f7ee;color:#166534}} .error{{background:#fff0f0;color:#991b1b}}
.pill{{display:inline-block;padding:3px 8px;border-radius:20px;background:#eef2ff;color:#3730a3;font-size:12px;white-space:nowrap}}
.pill.resolved{{background:#dcfce7;color:#166534}} .pill.progress{{background:#fef3c7;color:#92400e}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}} .stat{{background:#f8fafc;border:1px solid var(--line);border-radius:9px;padding:10px 13px;min-width:120px}}
.stat strong{{display:block;font-size:22px}} .actions{{display:flex;gap:8px;flex-wrap:wrap}} .small{{font-size:12px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}} .wide{{grid-column:auto}} header h1{{font-size:21px}}}}
</style>
</head>
<body>
<header><h1>Campus Complaint Tracker</h1><p>RGUKT Ongole · Local maintenance complaint desk</p></header>
<main>{banner}{body}</main>
</body></html>"""


def status_pill(status):
    cls = "resolved" if status == "Resolved" else ("progress" if status == "In progress" else "")
    return f'<span class="pill {cls}">{esc(status)}</span>'


def render_tickets(tickets):
    if not tickets:
        return '<p class="muted">No complaints have been submitted yet.</p>'
    rows = []
    for t in sorted(tickets, key=lambda x: x["id"], reverse=True):
        rows.append(
            "<tr>"
            f'<td>#{t["id"]}</td><td>{esc(t["category"])}</td><td>{esc(t["location"])}</td>'
            f'<td>{esc(t["description"])}</td><td>{status_pill(t["status"])}</td>'
            f'<td>{esc(t["created"])}</td><td><a href="/?history={t["id"]}">History</a></td>'
            "</tr>"
        )
    return '<div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Category</th><th>Location</th><th>Description</th><th>Status</th><th>Created</th><th>History</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def render_summary(tickets):
    summary = {}
    for t in tickets:
        if t["status"] == "Resolved":
            continue
        category = t["category"]
        age = ticket_age(t)
        count, oldest = summary.get(category, (0, 0))
        summary[category] = (count + 1, max(oldest, age))
    if not summary:
        return '<p class="muted">There are currently no open complaints.</p>'
    rows = "".join(
        f"<tr><td>{esc(category)}</td><td>{count}</td><td>{oldest}</td></tr>"
        for category, (count, oldest) in sorted(summary.items())
    )
    return '<div class="table-wrap"><table><thead><tr><th>Category</th><th>Open tickets</th><th>Oldest age (days)</th></tr></thead><tbody>' + rows + "</tbody></table></div>"


def render_history(ticket):
    rows = "".join(
        f"<tr><td>{esc(item[0])}</td><td>{status_pill(item[1])}</td><td>{esc(item[2])}</td></tr>"
        for item in ticket["history"]
    )
    return (
        f'<section class="card wide"><h2>History for ticket #{ticket["id"]}</h2>'
        f'<p><strong>{esc(ticket["category"])} · {esc(ticket["location"])}</strong> — {esc(ticket["description"])}</p>'
        '<div class="table-wrap"><table><thead><tr><th>Timestamp</th><th>Status</th><th>Comment</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div></section>"
    )


def render_home(data, message="", error=False):
    tickets = data["tickets"]
    categories = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in CATEGORIES)
    statuses = "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in STATUSES)
    open_count = sum(t["status"] != "Resolved" for t in tickets)
    total_count = len(tickets)
    body = f"""
<div class="stats">
 <div class="stat"><span class="muted small">Total tickets</span><strong>{total_count}</strong></div>
 <div class="stat"><span class="muted small">Open tickets</span><strong>{open_count}</strong></div>
 <div class="stat"><span class="muted small">Resolved</span><strong>{total_count-open_count}</strong></div>
</div>
<div class="grid">
 <section class="card"><h2>Submit a complaint</h2>
 <form method="post" action="/add">
  <label>Category</label><select name="category" required>{categories}</select>
  <label>Location</label><input name="location" placeholder="e.g. Block A, Room 12" required>
  <label>Complaint description</label><textarea name="description" placeholder="Describe the maintenance issue..." required></textarea>
  <button type="submit">Submit complaint</button>
 </form></section>
 <section class="card"><h2>Search complaints</h2>
 <form method="get" action="/">
  <label>Search by location or complaint text</label>
  <input name="q" placeholder="Try fan or Block A">
  <button type="submit">Search</button>
  <a class="button secondary" href="/">Clear</a>
 </form>
 <p class="muted small">Search is case-insensitive and checks location and description.</p>
 </section>
 <section class="card"><h2>Update ticket status</h2>
 <form method="post" action="/update">
  <label>Ticket number</label><input type="number" name="ticket_id" min="1" placeholder="e.g. 1" required>
  <label>New status</label><select name="status" required>{statuses}</select>
  <label>Update comment (required)</label><input name="comment" placeholder="e.g. Assigned to technician" required>
  <button type="submit">Record update</button>
 </form>
 <p class="muted small">Select Pending to reopen a resolved ticket. Previous history is preserved.</p>
 </section>
 <section class="card"><h2>Open complaint summary</h2>{render_summary(tickets)}</section>
 <section class="card wide"><h2>All complaints</h2>{render_tickets(tickets)}</section>
"""
    query = ""
    # Search result section is inserted by handler when needed.
    return page("Campus Complaint Tracker", body + "</div>", message, error)


class Handler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200):
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def do_GET(self):
        data = load_data()
        params = parse_qs(urlparse(self.path).query)
        if "history" in params:
            try:
                ticket_id = int(params["history"][0])
            except ValueError:
                ticket_id = -1
            ticket = next((t for t in data["tickets"] if t["id"] == ticket_id), None)
            if ticket is None:
                self.send_html(page("Not found", '<section class="card"><h2>Ticket not found</h2><a href="/">Back</a></section>', "Unknown ticket number.", True), 404)
                return
            body = '<div class="grid">' + render_history(ticket) + '<section class="card wide"><a class="button secondary" href="/">Back to dashboard</a></section></div>'
            self.send_html(page(f"Ticket {ticket_id} history", body))
            return
        q = params.get("q", [""])[0].strip()
        if q:
            needle = q.casefold()
            matches = [t for t in data["tickets"] if needle in (t["location"] + " " + t["description"]).casefold()]
            rows = "".join(
                f'<tr><td>#{t["id"]}</td><td>{esc(t["location"])}</td><td>{esc(t["description"])}</td><td>{status_pill(t["status"])}</td><td><a href="/?history={t["id"]}">History</a></td></tr>'
                for t in matches
            ) or '<tr><td colspan="5">No matching complaints found.</td></tr>'
            result = f'<section class="card wide"><h2>Search results for “{esc(q)}”</h2><div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Location</th><th>Description</th><th>Status</th><th>History</th></tr></thead><tbody>{rows}</tbody></table></div><a class="button secondary" href="/">Back</a></section>'
            self.send_html(render_home(data).replace("</div></main>", result + "</div></main>"))
            return
        self.send_html(render_home(data))

    def do_POST(self):
        data = load_data()
        form = self.read_form()
        try:
            if self.path == "/add":
                category = form.get("category", "")
                location = form.get("location", "").strip()
                description = form.get("description", "").strip()
                if category not in CATEGORIES or not location or not description:
                    raise ValueError("Enter a valid category, location and complaint description.")
                ticket = {
                    "id": max((t["id"] for t in data["tickets"]), default=0) + 1,
                    "category": category,
                    "location": location,
                    "description": description,
                    "status": "Pending",
                    "created": date.today().isoformat(),
                    "history": [[datetime.now().isoformat(timespec="seconds"), "Pending", "Ticket created"]],
                }
                possible = duplicates(ticket, data["tickets"])
                data["tickets"].append(ticket)  # Keep both tickets; never auto-merge.
                save_data(data)
                if possible:
                    items = "".join(
                        f'<tr><td>#{old["id"]}</td><td>{esc(old["description"])}</td><td>{score:.0%}</td></tr>'
                        for old, score in possible
                    )
                    suggestion = '<section class="card wide"><h2>Possible earlier complaints</h2><p>The new ticket was saved. These are suggestions only; both tickets remain separate.</p><div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Description</th><th>Similarity</th></tr></thead><tbody>' + items + "</tbody></table></div></section>"
                    self.send_html(render_home(data, f'Complaint submitted as ticket #{ticket["id"]}. Possible duplicates found.') .replace("</div></main>", suggestion + "</div></main>"))
                else:
                    self.send_html(render_home(data, f'Complaint submitted successfully as ticket #{ticket["id"]}.'))
                return

            if self.path == "/update":
                try:
                    ticket_id = int(form.get("ticket_id", ""))
                except ValueError:
                    raise ValueError("Enter a valid ticket number.")
                ticket = next((t for t in data["tickets"] if t["id"] == ticket_id), None)
                if ticket is None:
                    raise ValueError("Ticket does not exist.")
                status = form.get("status", "")
                comment = form.get("comment", "").strip()
                if status not in STATUSES or not comment:
                    raise ValueError("Choose a valid status and enter a nonempty update comment.")
                ticket["status"] = status
                ticket["history"].append([datetime.now().isoformat(timespec="seconds"), status, comment])
                save_data(data)
                self.send_html(render_home(data, f'Ticket #{ticket_id} updated to {status}.'))
                return
            self.send_html(render_home(data, "Unknown action.", True), 400)
        except ValueError as exc:
            self.send_html(render_home(data, str(exc), True), 400)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        save_data({"tickets": []})
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Campus Complaint Tracker is running.")
    print(f"Open http://{HOST}:{PORT} in your browser.")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
