# Mist Org Access Report

Lists every Juniper Mist org each of your API keys can reach, on every cloud, with the access level.

For every API key in the ini, the script calls `GET /api/v1/self` on that key's cloud and reports each privilege the key holds:

- **Role**: admin, write, read, helpdesk or installer
- **Scope**: `org`, `site`, `orgsites` (a subset of an org's sites), `msp`, or `super`
- Org (or site/MSP) name and ID
- The MSP the org belongs to, if any
- **Views** that limit the role, e.g. `super_observer` or `org_network_admin`

Super accounts are supported. A `super` privilege gives access to every org on that cloud, so it is reported as one row, **(all orgs on cloud - super)**, and shown in its own *Super access* column. It is not counted in the listed-org total.

The script is read-only and makes one API call per key.

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
  Global_01  api.mist.com      you@example.com  1 + all (super read)  admin=1, read=1  OK
  EMEA_01    api.eu.mist.com   you@example.com  120                   admin=7, read=113 OK
```

### Excel workbook (`--xlsx`)

- **Summary**: one row per key, with cloud, user, super access, number of listed orgs, the number of entries for each role, and the result. A Total row adds up the counts, and keys that failed are shaded red. The sheet also shows the source ini and when it was generated.
- **All Access**: one row per privilege, with key, cloud, user, org/object, ID, role, scope, MSP, views and note. The Role cell is coloured: green for admin, yellow for write, blue for read. Every column can be filtered and the header row stays visible when you scroll.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All keys answered |
| 1 | At least one key failed (bad token, network error, etc.). The other keys are still reported. |
| 2 | The ini could not be read, or it has no sections with both cloud and token |

## Notes

- Org API tokens have no user, so they are shown as `(org token)`.
- Access is taken from the key's `/self` privileges. To list each org individually under a super account you would need the org list from the Mist super endpoints, which this tool does not call.
