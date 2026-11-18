#!/usr/bin/env python3
"""List every Mist org reachable by each API key in a credential ini, with access level.

For each token section ([name] with cloud + token) the script calls
GET /api/v1/self on that key's cloud and reports every privilege entry:
org / site / orgsites / msp scope, org name + id, role (admin/write/read/
helpdesk/installer...) and any limiting views.

Usage:
    python3 mist_org_access_report.py [--ini PATH] [--csv OUT.csv] [--xlsx [OUT.xlsx]]

Exit code 0 = all keys answered, 1 = at least one key failed, 2 = bad ini.
"""
import argparse
import configparser
import csv
import os
import sys
from datetime import datetime

import requests

DEFAULT_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "mist_org_access_report.ini")
RESERVED = {"account", "network"}
ROLE_ORDER = {"admin": 0, "write": 1, "read": 2, "helpdesk": 3, "installer": 4}


def build_session(cfg):
    s = requests.Session()
    if cfg.has_section("network"):
        net = cfg["network"]
        ca = net.get("ca_bundle", "").strip()
        if ca:
            s.verify = os.path.expanduser(ca)
        elif not net.getboolean("verify_ssl", fallback=True):
            s.verify = False
            requests.packages.urllib3.disable_warnings()
        proxies = {k: net.get(f"{k}_proxy", "").strip() for k in ("http", "https")}
        proxies = {k: v for k, v in proxies.items() if v}
        if proxies:
            s.proxies.update(proxies)
    return s


def fetch_self(session, cloud, token):
    """Return (self_json, error)."""
    try:
        resp = session.get(f"https://{cloud}/api/v1/self",
                           headers={"Authorization": f"Token {token}"}, timeout=30)
    except requests.exceptions.SSLError:
        return None, "SSL error - set [network] ca_bundle"
    except requests.exceptions.ProxyError:
        return None, "Proxy error - check [network] proxies"
    except requests.exceptions.RequestException as e:
        return None, type(e).__name__
    if resp.status_code != 200:
        return None, f"/self HTTP {resp.status_code}"
    return resp.json(), ""


def privilege_rows(key, cloud, me):
    rows = []
    for p in me.get("privileges", []):
        scope = p.get("scope", "")
        if scope == "super":
            name, obj_id = "(all orgs on cloud - super)", ""
        elif scope == "msp":
            name, obj_id = p.get("name") or p.get("msp_name", ""), p.get("msp_id", "")
        elif scope == "site":
            name, obj_id = p.get("name", ""), p.get("site_id", "")
        else:  # org, orgsites, anything else org-anchored
            name, obj_id = p.get("name", ""), p.get("org_id", "")
        views = p.get("views") or []
        if isinstance(views, str):
            views = [views]
        extra = ""
        if scope == "orgsites" and p.get("site_ids"):
            extra = f"{len(p['site_ids'])} site(s)"
        rows.append({
            "key": key, "cloud": cloud, "email": me.get("email", "(org token)"),
            "scope": scope, "role": p.get("role", ""), "name": name, "id": obj_id,
            "org_id": p.get("org_id", ""), "msp": p.get("msp_name", ""),
            "views": ",".join(views), "note": extra,
        })
    rows.sort(key=lambda r: (ROLE_ORDER.get(r["role"], 9), r["name"].lower()))
    return rows


def print_table(headers, rows):
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def write_xlsx(path, ini, sections, summary, all_rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E78")
    role_fill = {"admin": "C6EFCE", "write": "FFEB9C", "read": "DDEBF7"}
    fail_fill = PatternFill("solid", fgColor="FFC7CE")

    def sheet(ws, headers, rows, widths=None):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = head_font, head_fill
            c.alignment = Alignment(vertical="center")
        for r in rows:
            ws.append(r)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, h in enumerate(headers, 1):
            vals = [len(str(h))] + [len(str(r[i - 1])) for r in rows if r[i - 1] is not None]
            ws.column_dimensions[get_column_letter(i)].width = min(max(vals) + 2, 60)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    roles = sorted({r["role"] for r in all_rows}, key=lambda x: ROLE_ORDER.get(x, 9))
    by_key = {}
    for r in all_rows:
        by_key.setdefault(r["key"], []).append(r)
    rows = []
    for key, cloud, email, _orgs, _roles, result in summary:
        kr = by_key.get(key, [])
        orgs = len({r["org_id"] or r["id"] for r in kr if r["scope"] != "super"}) \
            if result == "OK" else None
        sup = ",".join(r["role"] for r in kr if r["scope"] == "super") or None
        counts = [sum(1 for r in kr if r["role"] == role) if result == "OK" else None
                  for role in roles]
        rows.append([key, cloud, email if email != "-" else None, sup, orgs, *counts, result])
    sheet(ws, ["Key", "Cloud", "User", "Super access", "Listed orgs", *[f"{r.capitalize()}" for r in roles], "Result"], rows)
    total_row = len(rows) + 2
    ws.cell(total_row, 1, "Total").font = Font(bold=True)
    for col in range(5, 6 + len(roles)):
        L = get_column_letter(col)
        ws.cell(total_row, col, f"=SUM({L}2:{L}{total_row - 1})").font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, max_row=total_row - 1):
        if row[-1].value != "OK":
            for c in row:
                c.fill = fail_fill
    ws.cell(total_row + 2, 1, f"Source: {ini}")
    ws.cell(total_row + 3, 1, f"Generated: {datetime.now():%Y-%m-%d %H:%M}")

    ws = wb.create_sheet("All Access")
    headers = ["Key", "Cloud", "User", "Org / Object", "ID", "Role", "Scope",
               "MSP", "Views", "Note"]
    rows = [[r["key"], r["cloud"], r["email"], r["name"], r["id"], r["role"], r["scope"],
             r["msp"] or None, r["views"] or None, r["note"] or None]
            for r in sorted(all_rows, key=lambda r: (sections.index(r["key"]),
                                                     ROLE_ORDER.get(r["role"], 9),
                                                     r["name"].lower()))]
    sheet(ws, headers, rows)
    for row in ws.iter_rows(min_row=2):
        color = role_fill.get(row[5].value)
        if color:
            row[5].fill = PatternFill("solid", fgColor=color)

    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ini", default=DEFAULT_INI, help=f"credential ini (default {DEFAULT_INI})")
    ap.add_argument("--csv", help="also write all rows to this CSV file")
    ap.add_argument("--xlsx", nargs="?", const="",
                    help="also write an Excel workbook (default name "
                         "mist_org_access_YYYYMMDD_HHMM.xlsx in the current folder)")
    args = ap.parse_args()

    cfg = configparser.ConfigParser()
    if not cfg.read(args.ini):
        print(f"Cannot read {args.ini}", file=sys.stderr)
        return 2
    sections = [s for s in cfg.sections()
                if s.lower() not in RESERVED and cfg[s].get("cloud") and cfg[s].get("token")]
    if not sections:
        print(f"No token sections (cloud + token) found in {args.ini}", file=sys.stderr)
        return 2

    session = build_session(cfg)
    all_rows, summary, failed = [], [], []
    for s in sections:
        cloud, token = cfg[s]["cloud"].strip(), cfg[s]["token"].strip()
        me, err = fetch_self(session, cloud, token)
        print(f"\n=== {s}  ({cloud}) ===")
        if err:
            print(f"  FAILED: {err}")
            failed.append(s)
            summary.append([s, cloud, "-", "-", "-", f"FAIL: {err}"])
            continue
        rows = privilege_rows(s, cloud, me)
        all_rows.extend(rows)
        print(f"  User: {me.get('email', '(org token)')}   Privileges: {len(rows)}")
        if rows:
            print_table(["Role", "Scope", "Name", "ID", "MSP", "Views", "Note"],
                        [[r["role"], r["scope"], r["name"], r["id"], r["msp"] or "-",
                          r["views"] or "-", r["note"] or "-"] for r in rows])
        roles = {}
        for r in rows:
            roles[r["role"]] = roles.get(r["role"], 0) + 1
        role_txt = ", ".join(f"{k}={v}" for k, v in
                             sorted(roles.items(), key=lambda kv: ROLE_ORDER.get(kv[0], 9)))
        orgs = len({r["org_id"] or r["id"] for r in rows if r["scope"] != "super"})
        sup = ",".join(r["role"] for r in rows if r["scope"] == "super")
        orgs_txt = f"{orgs} + all (super {sup})" if sup else str(orgs)
        summary.append([s, cloud, me.get("email", "(org token)"), orgs_txt, role_txt or "-", "OK"])

    print("\n=== Summary ===")
    print_table(["Key", "Cloud", "User", "Orgs", "Roles", "Result"], summary)

    if args.csv:
        fields = ["key", "cloud", "email", "scope", "role", "name", "id",
                  "org_id", "msp", "views", "note"]
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nWrote {len(all_rows)} rows to {args.csv}")

    if args.xlsx is not None:
        path = args.xlsx or f"mist_org_access_{datetime.now():%Y%m%d_%H%M}.xlsx"
        write_xlsx(path, args.ini, sections, summary, all_rows)
        print(f"\nWrote Excel workbook {os.path.abspath(path)}")

    if failed:
        print(f"\n{len(failed)} of {len(sections)} keys failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
