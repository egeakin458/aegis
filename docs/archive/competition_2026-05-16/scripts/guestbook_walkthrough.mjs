// Drives the Aegis frontend through the guestbook benchmark, screenshotting each state.
// Submits the DDC directly via POST /api/pipeline/start, then opens /?run=<id> to watch.

import puppeteer from 'puppeteer'
import fs from 'fs'
import path from 'path'

const OUT_DIR = '/home/ege/projects/aegis/docs/guestbook_screenshots'
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:3000'
const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000'
const BENCHMARK = '/home/ege/projects/aegis/evaluation/benchmarks/benchmark_03_guestbook_ddc.json'

// Read API key from frontend env so the POST is authenticated.
const envFile = '/home/ege/projects/aegis/frontend/.env.local'
const envText = fs.readFileSync(envFile, 'utf8')
const apiKeyMatch = envText.match(/^NEXT_PUBLIC_API_KEY=(.+)$/m)
const API_KEY = apiKeyMatch ? apiKeyMatch[1].trim() : ''
if (!API_KEY) throw new Error('NEXT_PUBLIC_API_KEY not found in frontend/.env.local')

const benchmark = JSON.parse(fs.readFileSync(BENCHMARK, 'utf8'))
const ddc = benchmark.customer_config_v2

fs.mkdirSync(OUT_DIR, { recursive: true })

function ts() { return new Date().toISOString().slice(11, 19) }
function log(msg) { console.log(`[${ts()}] ${msg}`) }

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

let run_id = process.env.RUN_ID
if (run_id) {
  log(`attaching to existing run_id = ${run_id}`)
} else {
  log(`POST ${BACKEND}/api/pipeline/start`)
  const startResp = await fetch(`${BACKEND}/api/pipeline/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify(ddc),
  })
  if (!startResp.ok) {
    const txt = await startResp.text()
    throw new Error(`pipeline/start failed ${startResp.status}: ${txt}`)
  }
  const j = await startResp.json()
  run_id = j.run_id
  log(`run_id = ${run_id}`)
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
  // 01 — idle (open root with no ?run)
  log('open / (idle)')
  await page.goto(FRONTEND, { waitUntil: 'networkidle0', timeout: 30000 })
  await new Promise(r => setTimeout(r, 800))
  // Modal auto-opens on bare URL — close it for the idle shot
  await page.keyboard.press('Escape')
  await new Promise(r => setTimeout(r, 400))
  await shot(page, '01_idle')

  // 02 — intake modal open
  log('open intake modal')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent?.trim() === 'New Project')
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 600))
  await shot(page, '02_intake_modal_open')

  // Close modal — we already started the run via API
  await page.keyboard.press('Escape')
  await new Promise(r => setTimeout(r, 300))

  // 03 — navigate to ?run=<id> for live stream
  log(`open /?run=${run_id}`)
  await page.goto(`${FRONTEND}/?run=${run_id}`, { waitUntil: 'domcontentloaded' })
  await new Promise(r => setTimeout(r, 2500))
  await shot(page, '03_run_started')

  // Phase-aware sampler: shoot once per phase transition rather than fixed cadence.
  log('phase-aware sampling')
  const phaseTargets = [
    { name: '04_ra_running',           match: ['Project Analyst started', 'analyst is reviewing', 'analyst is thinking'] },
    { name: '05_ra_complete',          match: ['Project Analyst complete', 'project brief'] },
    { name: '06_sa_running',           match: ['Solution Architect started', 'architect is designing', 'architect is thinking'] },
    { name: '07_sa_complete',          match: ['Solution Architect complete'] },
    { name: '08_dev_running',          match: ['Developer started', 'developer is building'] },
    { name: '09_dev_complete',         match: ['Developer complete'] },
    { name: '10_build_check',          match: ['BUILD CHECK', 'Verifying the generated code'] },
    { name: '11_qa_running',           match: ['QA Reviewer started', 'reviewer is checking'] },
    { name: '12_pipeline_complete',    match: ['Pipeline Complete', 'Built with caveats'] },
  ]
  const captured = new Set()
  const tStart = Date.now()
  let done = false
  while (!done && Date.now() - tStart < 360000) {
    const body = await page.evaluate(() => document.body.innerText)
    for (const t of phaseTargets) {
      if (captured.has(t.name)) continue
      if (t.match.some(m => body.includes(m))) {
        await shot(page, t.name)
        captured.add(t.name)
      }
    }
    if (captured.has('12_pipeline_complete')) {
      done = true
      break
    }
    await new Promise(r => setTimeout(r, 1500))
  }

  if (!done) {
    log('waiting up to 5 more minutes for completion')
    await waitForText(page, 'Pipeline Complete', 300000).catch(async () => {
      await waitForText(page, 'Built with caveats', 60000).catch(() => {})
    })
    await new Promise(r => setTimeout(r, 1200))
    await shot(page, '12_pipeline_complete')
  }

  log('open output viewer')
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find(b =>
      /view\s*file|view\s*files|view\s*output/i.test(b.textContent ?? '')
    )
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 1800))
  await shot(page, '13_output_viewer')

  // file open (default selection should already display a file)
  await new Promise(r => setTimeout(r, 600))
  await shot(page, '14_output_viewer_file_open')

  log('done')
} catch (e) {
  log(`ERROR: ${e.message}`)
  try { await shot(page, '99_error_state') } catch {}
  process.exitCode = 1
} finally {
  await browser.close()
}
