import type { WorkspaceTab } from "./WorkspaceTabs";

const registeredTabs = new Map<string, WorkspaceTab>();

export function registerWorkspaceTab(tab: WorkspaceTab): void {
  registeredTabs.set(tab.id, tab);
}

export function getRegisteredWorkspaceTabs(): WorkspaceTab[] {
  return Array.from(registeredTabs.values());
}
