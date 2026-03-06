import { defineConfig } from '@playwright/test'

export default defineConfig({
    testDir: './tests',
    timeout: 120_000,
    retries: 0,
    reporter: [
        ['html', { outputFolder: 'playwright-report' }],
        ['list'],
    ],
    use: {
        baseURL: 'http://localhost:9000',
        screenshot: 'on',
        video: 'on-first-retry',
        trace: 'on',
    },
    outputDir: 'test-results/',
})
