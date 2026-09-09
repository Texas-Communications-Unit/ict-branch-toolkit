import { readFileSync } from "node:fs";

import { expect, test } from "vitest";

test("serves third-party notices as static files without SPA fallback", () => {
  const nginxConfig = readFileSync("nginx.conf", "utf8");

  expect(nginxConfig).toContain("location ^~ /third-party/");
  expect(nginxConfig).toContain("try_files $uri =404;");
  expect(nginxConfig).toContain(
    'add_header X-Content-Type-Options "nosniff" always;',
  );
});
