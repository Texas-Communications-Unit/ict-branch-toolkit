# FCC reference search and capacity validation

Authenticated users with channel-library view permission can search the current imported FCC datasets at `/api/fcc-licenses/` and `/api/fcc-antenna-structures/`. The website exposes the same functions in the **FCC Reference** workspace. Searches are read-only and results include archive provenance.

Before any production import, copy an official archive to a temporary server location and run the no-write capacity probe:

```console
python manage.py probe_fcc_archive_capacity /temporary/path/l_LMpriv.zip --dataset uls_private
```

The JSON output reports archive digest, compressed and expanded sizes, expansion ratio, member count, available disk space, and confirms zero database writes. This validates archive structure and storage headroom; it does not import or reconcile records. Production import remains a separately approved operation.

FCC reference results are planning decision support. They do not authorize frequency use, transmission, coordination, or site access.
