// Drives the Aegis frontend with puppeteer, screenshots key UX states.
// Pipeline run takes ~4 min — script polls SSE-driven UI for state transitions.

import puppeteer from 'puppeteer'
import fs from 'fs'
import path from 'path'

const OUT_DIR = '/home/ege/projects/aegis/docs/ux_audit_screenshots'
const FRONTEND = 'http://localhost:3000'

const DESC = 'A personal task manager where a user can create tasks, mark them complete, and delete tasks they finished.'

function ts() {
  return new Date().toISOString().slice(11, 19)
}
function log(msg) {
  console.log(`[${ts()}] ${msg}`)
}
async function shot(page, name) {
  const file = path.join(OUT_DIR, `${name}.png`)
  await page.screenshot({ path: file, fullPage: false })
  log(`shot → ${name}.png`)
}
async function waitForText(page, text, timeoutMs = 600000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const body = await page.evaluate(() => document.body.innerText)
    if (body.includes(text)) return true
    await new Promise(r => setTimeout(r, 1000))
  }
  throw new Error(`Timed out waiting for "${text}"`)
}

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
  defaultViewport: { width: 1440, height: 900 },
})
const page = await browser.newPage()
page.on('console', m => log(`console.${m.type()}: ${m.text().slice(0, 200)}`))
page.on('pageerror', e => log(`pageerror: ${e.message}`))

try {
  log('open /')
  await page.goto(FRONTEND, { waitUntil: 'networkidle0', timeout: 30000 })
  await new Promise(r => setTimeout(r, 800))
  await shot(page, '01_idle')

  log('click New Project')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'New Project')
    if (!btn) throw new Error('New Project button not found')
    btn.click()
  })
  await new Promise(r => setTimeout(r, 500))
  await shot(page, '02_intake_modal_open')

  log('fill Quick intake')
  await page.evaluate((desc) => {
    const name = document.querySelector('input[placeholder="my-app"]')
    if (!name) throw new Error('name input not found')
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(name, 'taskmaster')
    name.dispatchEvent(new Event('input', { bubbles: true }))

    const ta = document.querySelector('textarea')
    if (!ta) throw new Error('description textarea not found')
    const taSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
    taSetter.call(ta, desc)
    ta.dispatchEvent(new Event('input', { bubbles: true }))
  }, DESC)
  await new Promise(r => setTimeout(r, 300))
  await shot(page, '03_intake_filled')

  log('click Start Pipeline')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Start Pipeline')
    if (!btn) throw new Error('Start Pipeline button not found')
    btn.click()
  })
  await new Promise(r => setTimeout(r, 3000))
  await shot(page, '04_pipeline_started')

  // Try to catch RA running
  await new Promise(r => setTimeout(r, 8000))
  await shot(page, '05_ra_running')

  // Catch clarification if it appears (poll up to 90s)
  log('watching for clarification or progress...')
  let clarShot = false
  const tStart = Date.now()
  while (Date.now() - tStart < 90000) {
    const body = await page.evaluate(() => document.body.innerText)
    if (body.includes('Clarification needed')) {
      await shot(page, '06_clarification_card')
      clarShot = true
      // Try filling answers with neutral text
      try {
        const filled = await page.evaluate(() => {
          const tas = [...document.querySelectorAll('textarea')].filter(t => t.placeholder === 'Your answer...')
          const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
          for (const t of tas) {
            setter.call(t, 'No preference, use a reasonable default.')
            t.dispatchEvent(new Event('input', { bubbles: true }))
          }
          return tas.length
        })
        log(`filled ${filled} clarification answers`)
        await new Promise(r => setTimeout(r, 300))
        await shot(page, '07_clarification_filled')
        await page.evaluate(() => {
          const btn = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'Submit Answers' && !b.disabled)
          if (btn) btn.click()
        })
        await new Promise(r => setTimeout(r, 2000))
        await shot(page, '08_after_clarification_submit')
      } catch (e) {
        log(`clarification fill error: ${e.message}`)
      }
      break
    }
    if (body.includes('Designing') || body.includes('Building') || body.includes('Reviewing')) {
      log('skipped clarification — advancing to next phase')
      break
    }
    await new Promise(r => setTimeout(r, 2000))
  }

  // Sample shots through the run
  log('sampling mid-run states')
  for (let i = 0; i < 6; i++) {
    await new Promise(r => setTimeout(r, 30000))
    await shot(page, `09_midrun_${i}`)
    const body = await page.evaluate(() => document.body.innerText)
    if (body.includes('Pipeline Complete') || body.includes('Built with caveats')) {
      log('pipeline finished')
      break
    }
  }

  log('waiting for completion (up to 8 min total)')
  await waitForText(page, 'Pipeline Complete', 480000).catch(async () => {
    log('falling back: maybe partial')
    await waitForText(page, 'Built with caveats', 60000)
  })
  await new Promise(r => setTimeout(r, 1500))
  await shot(page, '10_complete')

  log('click View File Tree')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'View File Tree')
    if (!btn) throw new Error('View File Tree button not found')
    btn.click()
  })
  await new Promise(r => setTimeout(r, 1500))
  await shot(page, '11_output_viewer')

  // Open a file
  await page.evaluate(() => {
    const fileBtn = [...document.querySelectorAll('button')].find(b => /package\.json|page\.tsx|README/i.test(b.textContent ?? ''))
    if (fileBtn) fileBtn.click()
  })
  await new Promise(r => setTimeout(r, 800))
  await shot(page, '12_output_viewer_file_open')

  log('done')
} catch (e) {
  log(`ERROR: ${e.message}`)
  try { await shot(page, '99_error_state') } catch {}
  process.exitCode = 1
} finally {
  await browser.close()
}
