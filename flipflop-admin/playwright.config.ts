import { defineConfig, devices } from '@playwright/test';

const webServerCommand = process.platform === 'win32'
  ? 'set NEXT_PUBLIC_API_URL=/api&& set ADMIN_JWT_SECRET=playwright-test-secret&& set PLAYWRIGHT_TEST=1&& npm run build&& set NEXT_PUBLIC_API_URL=/api&& set ADMIN_JWT_SECRET=playwright-test-secret&& set PLAYWRIGHT_TEST=1&& npm run start -- -p 4173 -H 127.0.0.1'
  : 'NEXT_PUBLIC_API_URL=/api ADMIN_JWT_SECRET=playwright-test-secret PLAYWRIGHT_TEST=1 npm run build && NEXT_PUBLIC_API_URL=/api ADMIN_JWT_SECRET=playwright-test-secret PLAYWRIGHT_TEST=1 npm run start -- -p 4173 -H 127.0.0.1';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: webServerCommand,
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 180_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
