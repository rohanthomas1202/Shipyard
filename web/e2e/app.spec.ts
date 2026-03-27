import { test, expect } from '@playwright/test'

test.describe('Shipyard App', () => {

  test('loads the home screen', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=What are we building today?')).toBeVisible()
  })

  test('shows the three-panel layout', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('EXPLORER')).toBeVisible()
    await expect(page.locator('textarea')).toBeVisible()
    await expect(page.getByText('AGENT')).toBeVisible()
  })

  test('shows "No project selected" in file tree', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('paragraph').filter({ hasText: 'No project selected' })).toBeVisible()
  })

  test('shows run status as Idle', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Idle')).toBeVisible()
  })

  test('mesh background blobs are rendered', async ({ page }) => {
    await page.goto('/')
    const blobs = page.locator('div[style*="blur(120px)"]')
    await expect(blobs).toHaveCount(3)
  })

  test('quick action buttons are visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('button', { name: /Create new project/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Workspace settings/ })).toBeVisible()
  })

  test('clicking "Create new project" opens project picker', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Create new project/ }).click()
    await expect(page.getByRole('heading', { name: 'Select Project' })).toBeVisible()
  })

  test('project picker shows both tabs', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Create new project/ }).click()
    await expect(page.getByText('Existing Projects')).toBeVisible()
    await expect(page.getByRole('button', { name: 'New Project', exact: true })).toBeVisible()
  })

  test('can create a new project via picker', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Create new project/ }).click()

    // Switch to New Project tab
    await page.getByRole('button', { name: 'New Project', exact: true }).click()

    // Fill in project details
    await page.locator('input[placeholder="my-project"]').fill('e2e-test-' + Date.now())
    await page.locator('input[placeholder*="/Users"]').fill('/tmp/e2e-test')

    // Create
    await page.getByRole('button', { name: 'Create Project' }).click()

    // Picker should close and project name should appear in sidebar
    await expect(page.locator('text=e2e-test-')).toBeVisible({ timeout: 5000 })
  })

  test('top bar is visible with project selector and instruction input', async ({ page }) => {
    await page.goto('/')
    // Project selector button
    await expect(page.getByText('Select project...')).toBeVisible()
    // Instruction input textarea in top bar
    await expect(page.locator('textarea[placeholder*="Describe the code change"]')).toBeVisible()
    // Run status indicator
    await expect(page.getByText('Idle')).toBeVisible()
  })

  test('prompt textarea accepts input', async ({ page }) => {
    await page.goto('/')
    // The top bar textarea
    const textarea = page.locator('textarea[placeholder*="Describe the code change"]')
    await textarea.fill('Refactor the auth module')
    await expect(textarea).toHaveValue('Refactor the auth module')
  })

  test('instruction input expands on focus', async ({ page }) => {
    await page.goto('/')
    const textarea = page.locator('textarea[placeholder*="Describe the code change"]')
    await textarea.click()
    // After focus, the expanded placeholder should appear
    await expect(page.locator('textarea[placeholder*="Be specific about files"]')).toBeVisible()
    // The "Run instruction" button should appear
    await expect(page.getByRole('button', { name: 'Run instruction' })).toBeVisible()
  })

  test('Run instruction button is disabled when input is empty', async ({ page }) => {
    await page.goto('/')
    const textarea = page.locator('textarea[placeholder*="Describe the code change"]')
    await textarea.click()
    const runBtn = page.getByRole('button', { name: 'Run instruction' })
    await expect(runBtn).toBeDisabled()
  })

  test('settings modal requires a project', async ({ page }) => {
    // Create and select a project first
    const projName = 'pw-settings-' + Date.now()
    await page.request.post('/projects', {
      data: { name: projName, path: '/tmp/pw-settings' },
    })

    await page.goto('/')
    // Open project picker from quick actions
    await page.getByRole('button', { name: /Create new project/ }).click()
    await expect(page.getByText(projName)).toBeVisible({ timeout: 5000 })
    await page.getByText(projName).click()

    // Now open settings
    await page.getByRole('button', { name: /Workspace settings/ }).click()
    await expect(page.getByRole('heading', { name: 'Project Settings' })).toBeVisible({ timeout: 5000 })

    // Close via Escape
    await page.keyboard.press('Escape')
    await expect(page.getByRole('heading', { name: 'Project Settings' })).not.toBeVisible()
  })

  test('welcome card is visible in agent panel', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Welcome to your workspace.')).toBeVisible()
  })

  test('health endpoint returns ok', async ({ page }) => {
    const res = await page.request.get('/health')
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.status).toBe('ok')
  })

  test('projects API works', async ({ page }) => {
    const res = await page.request.get('/projects')
    expect(res.ok()).toBeTruthy()
    const projects = await res.json()
    expect(Array.isArray(projects)).toBeTruthy()
  })

  test('project responses do not contain github_pat', async ({ page }) => {
    await page.request.post('/projects', {
      data: { name: 'pat-test-' + Date.now(), path: '/tmp/pat' },
    })

    const res = await page.request.get('/projects')
    const projects = await res.json()
    for (const p of projects) {
      expect(p.github_pat).toBeUndefined()
    }
  })
})
