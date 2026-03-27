import { test, expect } from '@playwright/test'

test.describe('Activity Stream', () => {

  test('timeline renders empty state when no runs exist', async ({ page }) => {
    await page.goto('/')
    // After Plan 02 rewrites AgentPanel, the empty state shows "No activity yet"
    await expect(page.getByText('No activity yet')).toBeVisible()
  })

  test('scroll badge is not visible when at bottom of stream', async ({ page }) => {
    await page.goto('/')
    // The NewEventBadge should not render when there are no new events
    // (count <= 0 returns null)
    const badge = page.locator('button[role="status"]')
    await expect(badge).toHaveCount(0)
  })

})
