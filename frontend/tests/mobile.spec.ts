import { expect, Page, test } from "@playwright/test";

const shots = process.env.SHOTS_DIR;

async function shot(page: Page, name: string, project: string) {
  if (shots) await page.screenshot({ path: `${shots}/${project}-${name}.png`, fullPage: true });
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test("brief, event, company, ask", async ({ page }, info) => {
  const p = info.project.name;
  await page.goto("/");
  await expect(page.getByText(/Needs you (today|in this window) \(\d+\)/)).toBeVisible({ timeout: 30_000 });
  await noHorizontalScroll(page);
  await shot(page, "brief", p);

  const firstEvent = page.locator('a[href^="/event/"]').first();
  if (await firstEvent.count()) {
    await firstEvent.click();
    await expect(page.getByText(/Why this is here/).first()).toBeVisible();
    await noHorizontalScroll(page);
    await shot(page, "event", p);
  }

  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio" })).toBeVisible();
  await shot(page, "portfolio", p);

  await page.goto("/research");
  const ready = page.locator('a[href^="/company/"]').first();
  await expect(ready).toBeVisible({ timeout: 15_000 });
  await ready.click();
  await expect(page.getByRole("radiogroup", { name: "Company sections" })).toBeVisible();
  await page.waitForTimeout(800);
  await noHorizontalScroll(page);
  await shot(page, "company", p);

  await page.getByRole("button", { name: "Ask FINN" }).click();
  await expect(page.getByRole("dialog", { name: "Ask FINN" })).toBeVisible();
  await page.getByRole("textbox", { name: "Your question" }).fill("What did management guide for margins?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Reading the sources/)).toBeHidden({ timeout: 30_000 });
  await shot(page, "ask", p);

  await page.goto("/alerts");
  await expect(page.getByText("What counts as unusual")).toBeVisible();
  await noHorizontalScroll(page);
  await shot(page, "alerts", p);
});
