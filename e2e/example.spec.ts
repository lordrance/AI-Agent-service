import { test, expect } from "@playwright/test";

// Skipped by default so `pnpm e2e` passes on an empty template.
// Once your app is running on http://localhost:5173, change `test.skip` to `test`
// (or delete this file and write your own specs).
test.skip("smoke: the app loads", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/./);
});
