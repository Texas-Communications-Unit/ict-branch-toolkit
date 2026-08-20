import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WorkspaceTabs } from "../src/WorkspaceTabs";

test("provides keyboard-operable workspace tabs", async () => {
  render(
    <WorkspaceTabs
      initialTab="ics-205"
      tabs={[
        {
          id: "incidents",
          label: "Incidents",
          content: <p>Incident content</p>,
        },
        { id: "ics-205", label: "ICS 205", content: <p>Plan content</p> },
        { id: "map", label: "Map", content: <p>Map content</p> },
        {
          id: "resources",
          label: "Resources",
          content: <p>Resources content</p>,
        },
      ]}
    />,
  );

  const icsTab = screen.getByRole("tab", { name: "ICS 205" });
  const mapTab = screen.getByRole("tab", { name: "Map" });
  expect(icsTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel", { name: "ICS 205" })).toBeVisible();
  expect(
    screen.queryByRole("tabpanel", { name: "Map" }),
  ).not.toBeInTheDocument();

  icsTab.focus();
  await userEvent.keyboard("{ArrowRight}");
  expect(mapTab).toHaveFocus();
  expect(mapTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel", { name: "Map" })).toBeVisible();

  await userEvent.keyboard("{End}");
  expect(screen.getByRole("tab", { name: "Resources" })).toHaveFocus();
  await userEvent.keyboard("{Home}");
  expect(screen.getByRole("tab", { name: "Incidents" })).toHaveFocus();
});
