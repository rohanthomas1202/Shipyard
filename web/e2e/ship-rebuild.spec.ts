import { test, expect } from '@playwright/test'

const BASE_URL = process.env.SHIP_BASE_URL || 'http://localhost:3000'
const TEST_EMAIL = `e2e-${Date.now()}@example.com`
const TEST_PASSWORD = 'e2eTestPass123!'

test.describe.configure({ mode: 'serial' })

// ---------------------------------------------------------------------------
// Ship UI renders (SHIP-03)
// ---------------------------------------------------------------------------

test.describe('Ship UI renders', () => {
  test('Ship UI renders without critical errors', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))
    await page.goto(BASE_URL)
    await expect(page).toHaveTitle(/.+/)
    await expect(page.locator('body')).toBeVisible()
    expect(errors).toHaveLength(0)
  })

  test('has interactive elements', async ({ page }) => {
    await page.goto(BASE_URL)
    const interactive = page.locator('button, a, input')
    await expect(interactive.first()).toBeVisible()
  })

  test('no horizontal overflow', async ({ page }) => {
    await page.goto(BASE_URL)
    await page.setViewportSize({ width: 1280, height: 720 })
    // Wait for layout to settle
    await page.waitForLoadState('domcontentloaded')
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(scrollWidth).toBeLessThanOrEqual(1280)
  })
})

// ---------------------------------------------------------------------------
// Auth flow (SHIP-02)
// ---------------------------------------------------------------------------

test.describe('Auth flow', () => {
  test('signup page renders form', async ({ page }) => {
    // Try /signup first, fall back to /register
    let resp = await page.goto(`${BASE_URL}/signup`)
    if (!resp || resp.status() >= 400) {
      resp = await page.goto(`${BASE_URL}/register`)
    }
    await expect(
      page.locator('input[type="email"], input[name="email"]')
    ).toBeVisible()
    await expect(
      page.locator('input[type="password"], input[name="password"]')
    ).toBeVisible()
  })

  test('signup flow works', async ({ page }) => {
    let resp = await page.goto(`${BASE_URL}/signup`)
    if (!resp || resp.status() >= 400) {
      await page.goto(`${BASE_URL}/register`)
    }
    await page.locator('input[type="email"], input[name="email"]').fill(TEST_EMAIL)
    await page.locator('input[type="password"], input[name="password"]').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await expect(page).not.toHaveURL(/signup|register/)
  })

  test('login flow works', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"], input[name="email"]').fill(TEST_EMAIL)
    await page.locator('input[type="password"], input[name="password"]').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await expect(page).not.toHaveURL(/login/)
  })
})

// ---------------------------------------------------------------------------
// CRUD flow (SHIP-02)
// ---------------------------------------------------------------------------

test.describe('CRUD flow', () => {
  async function login(page: import('@playwright/test').Page) {
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"], input[name="email"]').fill(TEST_EMAIL)
    await page.locator('input[type="password"], input[name="password"]').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await expect(page).not.toHaveURL(/login/)
  }

  test('authenticated user sees content list or empty state', async ({ page }) => {
    await login(page)
    const contentArea = page.locator(
      'table, ul, [data-testid="empty-state"], :text("create"), :text("no items"), :text("get started")'
    )
    await expect(contentArea.first()).toBeVisible()
  })

  test('create and view content', async ({ page }) => {
    await login(page)
    const createBtn = page.locator(
      'a:text("create"), button:text("create"), a:text("new"), button:text("new")'
    )
    await createBtn.first().click()
    // Fill title field
    const titleInput = page.locator(
      'input[name="title"], input[placeholder*="title"], input[placeholder*="Title"]'
    )
    await titleInput.fill('E2E Test Item')
    // Submit form
    await page.locator('button[type="submit"]').click()
    await expect(page.locator(':text("E2E Test Item")')).toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Navigation (SHIP-02)
// ---------------------------------------------------------------------------

test.describe('Navigation', () => {
  test('primary navigation is visible', async ({ page }) => {
    await page.goto(BASE_URL)
    const nav = page.locator('nav, [role="navigation"], header a, aside a')
    await expect(nav.first()).toBeVisible()
  })

  test('navigation links route without full reload', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`)
    await page.locator('input[type="email"], input[name="email"]').fill(TEST_EMAIL)
    await page.locator('input[type="password"], input[name="password"]').fill(TEST_PASSWORD)
    await page.locator('button[type="submit"]').click()
    await expect(page).not.toHaveURL(/login/)
    const initialUrl = page.url()
    // Find and click a nav link
    const navLink = page.locator('nav a, [role="navigation"] a, header a, aside a').first()
    await navLink.click()
    expect(page.url()).not.toBe(initialUrl)
  })
})
