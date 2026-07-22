# Site crawler manifests

This directory registers administrator-controlled crawler executables with the
AI Enterprise OS control plane. A manifest does not make a generic crawler
understand a new website. The website-specific project must first implement the
standard command contract below.

## Command contract

The executable lives at `<root>/.venv/Scripts/<executable_name>` and may expose:

- `probe`: one low-volume availability and parser check.
- `inspect`: authenticated listing and download-control check.
- `login`: interactive login that persists the authorized browser session.
- `download --limit N --max-pages N`: download, deduplicate, upload to OSS, and
  import into the business database.

Commands must write UTF-8 logs, print a final JSON object, and use these exit
codes when relevant:

- `0`: completed.
- `2`: verification or interactive action required.
- `3`: OSS/database import failed.
- `4`: account quota exhausted.
- `5`: verification challenge timed out.

## Manifest

Copy `example.disabled.json` to `<site-id>.json`, edit it, and restart the
backend. Only trusted administrators should edit this directory because a
manifest registers a local executable.
