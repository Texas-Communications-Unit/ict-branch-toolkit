import { useEffect, useState } from "react";

import { getFccDatasetStatus } from "./api";
import type { FccDatasetStatus } from "./types";

const countLabels: Record<string, string> = {
  antenna_structures: "Antenna structures",
  licenses: "Licenses",
  locations: "Locations",
  frequencies: "Frequencies",
  emissions: "Emissions",
};

function date(value: string | null) {
  return value ? (
    <time dateTime={value}>{new Date(value).toLocaleString()}</time>
  ) : (
    "Not recorded"
  );
}

export function FccDatasetStatusPanel() {
  const [data, setData] = useState<FccDatasetStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    getFccDatasetStatus().then(
      (result) => {
        if (active) {
          setData(result);
          setLoading(false);
        }
      },
      () => {
        if (active) {
          setFailed(true);
          setLoading(false);
        }
      },
    );
    return () => {
      active = false;
    };
  }, [version]);

  function refresh() {
    setLoading(true);
    setFailed(false);
    setData(null);
    setVersion((value) => value + 1);
  }

  return (
    <section aria-labelledby="fcc-dataset-status-heading">
      <div className="section-heading">
        <h3 id="fcc-dataset-status-heading">FCC dataset status</h3>
        <button
          type="button"
          className="secondary-button"
          disabled={loading}
          onClick={refresh}
        >
          {failed ? "Retry dataset status" : "Refresh dataset status"}
        </button>
      </div>
      <p>
        These dates describe local reference imports, not FCC publication dates
        or current licensing validity. An old import may still match an
        unchanged source archive; the last source check is not recorded here.
      </p>
      {loading && <p role="status">Loading dataset status…</p>}
      {failed && (
        <p role="alert">
          Dataset status could not be loaded. FCC search is still available.
        </p>
      )}
      {data && (
        <>
          <p role="status">Status retrieved {date(data.generated_at)}.</p>
          <div className="resource-grid">
            {data.datasets.map((item) => (
              <article className="resource-card" key={item.dataset}>
                <h4>{item.label}</h4>
                {item.status === "not_imported" && (
                  <p>
                    No current import. This dataset is not available for
                    reference search.
                  </p>
                )}
                {item.status === "ambiguous" && (
                  <p>
                    Multiple imports are marked current. An administrator must
                    reconcile them before relying on this dataset.
                  </p>
                )}
                {item.status === "available" && (
                  <>
                    <p>Current local import</p>
                    {item.timestamp_warning ? (
                      <p>
                        Future import or retrieval date: verify the timestamp
                        before relying on its age.
                      </p>
                    ) : (
                      <p>
                        Archive retrieved {item.retrieved_age_days}{" "}
                        {item.retrieved_age_days === 1 ? "day" : "days"} ago.
                      </p>
                    )}
                    <dl className="coordinate-preview">
                      <div>
                        <dt>Archive retrieved</dt>
                        <dd>{date(item.retrieved_at)}</dd>
                      </div>
                      <div>
                        <dt>Imported</dt>
                        <dd>{date(item.imported_at)}</dd>
                      </div>
                      {Object.entries(item.record_counts).map(
                        ([key, count]) => (
                          <div key={key}>
                            <dt>{countLabels[key] ?? key}</dt>
                            <dd>
                              {count === null
                                ? "Not recorded"
                                : count.toLocaleString()}
                            </dd>
                          </div>
                        ),
                      )}
                    </dl>
                    <p>Counts describe records retained from this archive.</p>
                    <details>
                      <summary>Import provenance</summary>
                      <dl className="coordinate-preview">
                        <div>
                          <dt>Archive</dt>
                          <dd>{item.archive_name ?? "Not verified"}</dd>
                        </div>
                        <div>
                          <dt>Source</dt>
                          <dd>
                            {item.source_url ? (
                              <a href={item.source_url}>
                                Official FCC complete archive
                              </a>
                            ) : (
                              "Not verified"
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>Parser version</dt>
                          <dd>{item.parser_version ?? "Not recorded"}</dd>
                        </div>
                        <div>
                          <dt>SHA-256</dt>
                          <dd style={{ overflowWrap: "anywhere" }}>
                            {item.content_sha256 ?? "Not recorded"}
                          </dd>
                        </div>
                      </dl>
                    </details>
                  </>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
