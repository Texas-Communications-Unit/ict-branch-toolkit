import { useMemo } from "react";

import type { ConventionalChannel } from "./types";

type Props = {
  channels: ConventionalChannel[];
};

type ChannelGroup = {
  key: string;
  title: string;
  channels: ConventionalChannel[];
};

function formatFrequency(hz: number | null) {
  if (hz === null) return "—";
  return `${(hz / 1_000_000).toFixed(6)} MHz`;
}

function categoryTitle(channel: ConventionalChannel) {
  const sourceSection = channel.source_section.trim();
  if (sourceSection) return sourceSection;
  const channelUse = channel.channel_use.trim();
  if (channelUse) return channelUse;
  const band = channel.band.trim();
  return band ? `${band} interoperability channels` : "Other NIFOG channels";
}

function categoryKey(channel: ConventionalChannel) {
  return [channel.release.id, categoryTitle(channel)].join("::");
}

function groupNifogChannels(channels: ConventionalChannel[]): ChannelGroup[] {
  const grouped = new Map<string, ChannelGroup>();
  for (const channel of channels) {
    if (channel.release.source.source_type !== "cisa_nifog") continue;
    const key = categoryKey(channel);
    const current = grouped.get(key);
    if (current) {
      current.channels.push(channel);
    } else {
      grouped.set(key, {
        key,
        title: categoryTitle(channel),
        channels: [channel],
      });
    }
  }
  return Array.from(grouped.values()).sort((left, right) =>
    left.title.localeCompare(right.title, undefined, { numeric: true }),
  );
}

function sourceReference(channels: ConventionalChannel[]) {
  const first = channels[0];
  const pages = Array.from(
    new Set(channels.map((channel) => channel.source_pages.trim()).filter(Boolean)),
  ).join(", ");
  return {
    source: first.release.source.name,
    version: first.release.version,
    pages,
  };
}

export function NifogResourceCategories({ channels }: Props) {
  const groups = useMemo(() => groupNifogChannels(channels), [channels]);
  const otherChannels = useMemo(
    () =>
      channels.filter(
        (channel) => channel.release.source.source_type !== "cisa_nifog",
      ),
    [channels],
  );

  return (
    <div className="nifog-resource-categories">
      <h3>NIFOG interoperability channels</h3>
      <p className="empty">
        Categories follow the section metadata from the loaded NIFOG release. All
        categories are collapsed by default and may be opened independently.
      </p>
      {groups.length === 0 ? (
        <p className="empty">No NIFOG conventional channels match this search.</p>
      ) : (
        groups.map((group) => {
          const reference = sourceReference(group.channels);
          return (
            <details className="nifog-resource-category" key={group.key}>
              <summary>
                <strong>{group.title}</strong>
                <span className="count">{group.channels.length}</span>
              </summary>
              <p className="nifog-source-reference">
                Source: {reference.source} · release {reference.version}
                {reference.pages ? ` · page(s) ${reference.pages}` : ""}
              </p>
              <div
                className="nifog-table-scroll"
                role="region"
                aria-label={`${group.title} frequency table`}
                tabIndex={0}
              >
                <table className="nifog-frequency-table">
                  <thead>
                    <tr>
                      <th scope="col">Assignment</th>
                      <th scope="col">Channel Name</th>
                      <th scope="col">Mobile RX Frequency</th>
                      <th scope="col">Mobile RX CTCSS / NAC</th>
                      <th scope="col">Mobile TX Frequency</th>
                      <th scope="col">Mobile TX CTCSS / NAC</th>
                      <th scope="col">Authorized Emissions</th>
                      <th scope="col">Other Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.channels.map((channel) => (
                      <tr key={channel.id}>
                        <td>{channel.channel_use || "—"}</td>
                        <td>
                          <strong>{channel.name}</strong>
                          <br />
                          <small>{channel.identifier}</small>
                        </td>
                        <td>{formatFrequency(channel.rx_frequency_hz)}</td>
                        <td>{channel.rx_squelch || "—"}</td>
                        <td>{formatFrequency(channel.tx_frequency_hz)}</td>
                        <td>{channel.tx_squelch || "—"}</td>
                        <td>{channel.emission_designator || "—"}</td>
                        <td>
                          {[
                            channel.notes,
                            channel.restrictions,
                            channel.authorization,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="empty">
                Reference information only. Listing a channel does not itself
                authorize transmission; applicable licensing, coordination,
                agency policy, and NIFOG use conditions still apply.
              </p>
            </details>
          );
        })
      )}

      {otherChannels.length > 0 && (
        <details className="nifog-resource-category">
          <summary>
            <strong>Other conventional reference channels</strong>
            <span className="count">{otherChannels.length}</span>
          </summary>
          <div className="resource-grid">
            {otherChannels.map((channel) => (
              <article className="resource-card" key={channel.id}>
                <strong>
                  {channel.name} <small>({channel.identifier})</small>
                </strong>
                <span>
                  {formatFrequency(channel.rx_frequency_hz)} · {channel.mode}
                </span>
                {channel.channel_use && <span>{channel.channel_use}</span>}
                {channel.restrictions && (
                  <details>
                    <summary>Restrictions and use conditions</summary>
                    <p>{channel.restrictions}</p>
                  </details>
                )}
                <small>
                  {channel.release.source.name} · {channel.release.version}
                  {channel.source_pages ? ` · p. ${channel.source_pages}` : ""}
                </small>
              </article>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
