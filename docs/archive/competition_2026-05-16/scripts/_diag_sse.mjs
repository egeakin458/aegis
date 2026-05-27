import puppeteer from 'puppeteer'
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] })
const page = await browser.newPage()
const errors = []
page.on('requestfailed', r => errors.push(`FAIL ${r.url()} ${r.failure()?.errorText}`))
page.on('response', async r => {
  if (r.url().includes('/api/pipeline/') && r.url().includes('/events')) {
    console.log('SSE response status:', r.status(), r.url())
  }
})
await page.goto('http://localhost:3000/?run=447cd01d-4426-4a03-a339-ac94b405b78d', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
const info = await page.evaluate(() => ({
  apiKeySet: typeof (window).__NEXT_DATA__ !== 'undefined',
  body: document.body.innerText.slice(0, 400),
}))
console.log('body:', info.body)
console.log('errors:', errors)
await browser.close()
