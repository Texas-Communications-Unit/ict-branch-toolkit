# FCC reference search and capacity validation

Authenticated users with channel-library view permission can search the current imported FCC datasets at `/api/fcc-licenses/` and `/api/fcc-antenna-structures/`. The website exposes the same functions in the **FCC Reference** workspace. Searches are read-only and results include archive provenance.

Before any production import, copy an official archive to a temporary server location and run the no-write capacity probe:

```console
python manage.py probe_fcc_archive_capacity /temporary/path/l_LMpriv.zip --dataset uls_private
```

The JSON output reports archive digest, compressed and expanded sizes, expansion ratio, member count, available disk space, and confirms zero database writes. This validates archive structure and storage headroom; it does not import or reconcile records. Production import remains a separately approved operation.

For the shared-test server, an authorized maintainer can manually dispatch the
**Probe FCC archive capacity** workflow and select one dataset. The protected
`shared-test` environment approval remains required. The workflow downloads the
official archive to a mode-700 temporary server directory, runs the same
no-write probe in the deployed backend container, verifies
`database_writes=0`, and removes both server and container copies on exit.

FCC reference results are planning decision support. They do not authorize frequency use, transmission, coordination, or site access.
