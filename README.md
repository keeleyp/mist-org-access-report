# Mist Org Access Report

Lists every Juniper Mist org each of your API keys can reach, on every cloud, with the access level.

For every API key in the ini, the script calls `GET /api/v1/self` on that key's cloud and reports each privilege the key holds:

- **Role**: admin, write, read, helpdesk or installer
- **Scope**: `org`, `site`, `orgsites` (a subset of an org's sites), `msp`, or `super`
- Org (or site/MSP) name and ID
- The MSP the org belongs to, if any
- **Views** that limit the role, e.g. `super_observer` or `org_network_admin`

Super accounts are supported. A `super` privilege gives access to every org on that cloud. It is shown as one row, **(all orgs on cloud - super)**, in the key's table, and the script then lists every org the key can see:

- `GET /api/v1/super/orgs` for the orgs and `GET /api/v1/super/msps` for MSP names and tiers, paged at 1,000 per call
- One row per org, with org name and ID, MSP, MSP tier, created date, and the key's own direct role on that org, if it has one
- These rows go on a **Super Orgs** sheet in the workbook (`--xlsx`) or to `--super-csv`. The console just shows the count for each key.

The script is read-only. It makes one API call per key, plus about one call per 1,000 orgs for super keys. A full run across all 12 clouds with super keys lists about 94,000 orgs in under a minute.

**The script asks before listing the super orgs.** Once every key has been checked, it shows how many orgs each super key can see and roughly how many API calls the listing will take, then asks for confirmation:

```
=== Super access ===
  12 key(s) have super access and can see every org on their cloud:
    Global_01    api.mist.com         super read     27,094 orgs
    EMEA_01      api.eu.mist.com      super read     13,407 orgs
    ...
  Total: 94,267 orgs, about 112 API calls.
  List every org for these keys (Super Orgs sheet / --super-csv)? [y/N]
```

- Enter `y` to fetch the list. Anything else skips it, and super access is then reported as one row per key.
- `--super-orgs` says yes without asking, and `--no-super-orgs` says no without asking. Either one suits scheduled or scripted runs.
- When the script isn't run from a terminal and neither flag is given, it skips the list.
- If no key has super access, nothing is asked and the workbook has no Super Orgs sheet.

## Setup

```bash
pip install -r requirements.txt
cp mist_org_access_report.ini.example mist_org_access_report.ini
```

Edit `mist_org_access_report.ini` and paste a token into each cloud you want to check:

```ini
[EMEA_01]
cloud = api.eu.mist.com
token = YOUR_API_TOKEN
```

- The example has a section for every Mist cloud: api.mist.com, gc1, ac2, gc2, gc4, eu, gc3, ac6, gc6, ac5, gc5 and gc7.
- Sections with an empty `token` are skipped, so leave unused clouds blank.
- Section names are just labels. Add more sections to check several keys on the same cloud.
- `[account]` and `[network]` are reserved names and are never treated as keys.
- Your real `.ini` is listed in `.gitignore`, so it is never committed.

### Zscaler / proxy

If you are behind Zscaler or a proxy, fill in the optional `[network]` section:

```ini
[network]
ca_bundle = /path/to/zscaler-root.pem
# verify_ssl = false        # only if you have no CA bundle
https_proxy = http://proxy:8080
```

## Run

```bash
python3 mist_org_access_report.py
```

| Option | Meaning |
|---|---|
| `--ini PATH` | Use a different key file. Default: `mist_org_access_report.ini` next to the script. Any ini with `[label]` sections holding `cloud` + `token` works. |
| `--xlsx [OUT.xlsx]` | Also write an Excel workbook. With no name it saves `mist_org_access_YYYYMMDD_HHMM.xlsx` in the current folder. |
| `--csv OUT.csv` | Also write every privilege row to a CSV file. |
| `--super-csv OUT.csv` | Also write the super-key org list to a CSV file. |
| `--super-orgs` | List every org for super keys without asking. |
| `--no-super-orgs` | Don't list every org for super keys, and don't ask. Only the super privilege itself is reported. |

Example:

```bash
python3 mist_org_access_report.py --ini ~/keys/my_keys.ini --xlsx
```

## Output

### Console

There is one table per key, with admin rows first, then write, then read:

```
=== EMEA_02  (api.gc3.mist.com) ===
  User: you@example.com   Privileges: 3
  Role   Scope     Name                         ID          MSP          Views
  admin  org       Demo Org                     1d01a82a-…  -            -
  write  orgsites  Customer Org                 c23eeb51-…  -            org_network_admin
  read   super     (all orgs on cloud - super)              -            -
```

After that comes a summary with one line per key:

```
=== Summary ===
  Key        Cloud             User             Orgs                  Roles            Result
  Global_01  api.mist.com      you@example.com  1 + 27094 (super read)  admin=1, read=1  OK
  EMEA_01    api.eu.mist.com   you@example.com  120                   admin=7, read=113 OK
```

### Excel workbook (`--xlsx`)

- **Summary**: one row per key, with cloud, user, super access, number of listed orgs, number of super orgs, the number of entries for each role, and the result. A Total row adds up the counts, and keys that failed are shaded red. The sheet also shows the source ini and when it was generated.
- **All Access**: one row per privilege, with key, cloud, user, org/object, ID, role, scope, MSP, views and note. The Role cell is coloured: green for admin, yellow for write, blue for read. Every column can be filtered and the header row stays visible when you scroll.
- **Super Orgs** (only when a key has super access): one row per org, with key, cloud, super role, org, org ID, MSP, MSP ID, MSP tier, created date and direct role. *Direct role* is filled in when the key also has its own privilege on that org.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All keys answered |
| 1 | At least one key failed (bad token, network error, etc.). The other keys are still reported. |
| 2 | The ini could not be read, or it has no sections with both cloud and token |

## Notes

- Org API tokens have no user, so they are shown as `(org token)`.
- Access is taken from the key's `/self` privileges, plus the `/super/orgs` list for super keys.
- If the super org list can't be fetched for a key (for example HTTP 403), that key is marked FAIL and the exit code is 1.
- Control characters in org names, which Excel can't store, are removed in the workbook only. The CSV keeps the raw names.
