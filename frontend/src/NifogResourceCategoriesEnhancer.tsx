import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { listConventionalChannels } from "./api";
import { NifogResourceCategories } from "./NifogResourceCategories";
import type { ConventionalChannel } from "./types";

function matchesSearch(channel: ConventionalChannel, query: string) {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return true;
  return [
    channel.identifier,
    channel.name,
    channel.channel_use,
    channel.band,
    channel.jurisdiction,
    channel.eligibility,
    channel.authorization,
    channel.restrictions,
    channel.notes,
    channel.source_section,
    channel.source_pages,
    channel.release.source.name,
    channel.release.version,
  ]
    .join(" ")
    .toLocaleLowerCase()
    .includes(normalized);
}

export function NifogResourceCategoriesEnhancer() {
  const [mount, setMount] = useState<HTMLElement | null>(null);
  const [channels, setChannels] = useState<ConventionalChannel[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let input: HTMLInputElement | null = null;
    let panel: HTMLElement | null = null;

    const onSearch = () => setQuery(input?.value ?? "");
    const locate = () => {
      const heading = document.getElementById("library-heading");
      const nextPanel = heading?.closest<HTMLElement>("section.library-panel") ?? null;
      if (nextPanel === panel) return;

      if (input) input.removeEventListener("input", onSearch);
      panel?.classList.remove("nifog-categories-enhanced");
      panel = nextPanel;
      input = panel?.querySelector<HTMLInputElement>('input[type="search"]') ?? null;
      if (input) {
        setQuery(input.value);
        input.addEventListener("input", onSearch);
      }
      panel?.classList.add("nifog-categories-enhanced");
      setMount(panel);
    };

    locate();
    const observer = new MutationObserver(locate);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (input) input.removeEventListener("input", onSearch);
      panel?.classList.remove("nifog-categories-enhanced");
    };
  }, []);

  useEffect(() => {
    if (!mount) return;
    let active = true;
    void listConventionalChannels()
      .then((items) => {
        if (!active) return;
        setChannels(items);
        setError("");
      })
      .catch((caught) => {
        if (!active) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load categorized conventional channels.",
        );
      });
    return () => {
      active = false;
    };
  }, [mount]);

  if (!mount) return null;
  const visible = channels.filter((channel) => matchesSearch(channel, query));

  return createPortal(
    <section
      className="nifog-categorized-view"
      aria-labelledby="nifog-categorized-heading"
    >
      <h3 id="nifog-categorized-heading">Conventional channels by NIFOG category</h3>
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : (
        <NifogResourceCategories channels={visible} />
      )}
    </section>,
    mount,
  );
}
