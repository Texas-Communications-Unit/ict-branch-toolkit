import { useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

export interface WorkspaceTab {
  id: string;
  label: string;
  content: ReactNode;
  layout?: "grid" | "single";
}

interface WorkspaceTabsProps {
  tabs: WorkspaceTab[];
  initialTab: string;
}

export function WorkspaceTabs({ tabs, initialTab }: WorkspaceTabsProps) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function selectTab(index: number) {
    const tab = tabs[index];
    if (!tab) return;
    setActiveTab(tab.id);
    tabRefs.current[index]?.focus();
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    selectTab(nextIndex);
  }

  return (
    <>
      <nav
        className="workspace-navigation"
        aria-label="Planning workspace sections"
      >
        <div className="workspace-tablist" role="tablist">
          {tabs.map((tab, index) => {
            const selected = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                id={`workspace-tab-${tab.id}`}
                className="workspace-tab"
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`workspace-panel-${tab.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActiveTab(tab.id)}
                onKeyDown={(event) => handleKeyDown(event, index)}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </nav>
      {tabs.map((tab) => (
        <section
          key={tab.id}
          id={`workspace-panel-${tab.id}`}
          className={`workspace${tab.layout === "single" ? " workspace-single" : ""}`}
          role="tabpanel"
          aria-labelledby={`workspace-tab-${tab.id}`}
          hidden={tab.id !== activeTab}
        >
          {tab.content}
        </section>
      ))}
    </>
  );
}
