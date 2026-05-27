/**
 * Tests for the launcher API client.
 *
 * Node test env — no React rendering. Component-level behaviour is
 * verified manually per Phase C of plan_open_generated_app.md.
 *
 * These tests pin the URL + method contract so a backend rename or path
 * change is caught here, not at runtime.
 */

import { launchApp, stopApp, getLauncherState } from '@/lib/api/client'
import type { LaunchStatus } from '@/lib/types/api'

const BASE = 'http://localhost:8000/api/pipeline'

const idleStatus: LaunchStatus = {
  state: 'idle',
  run_id: null, port: null, url: null, pid: null, started_at: null, error: null,
}

function mockFetchOK(body: object) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response)
  ;(global as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch
  return fetchMock
}

function mockFetchError(status: number, body: string) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: 'Bad Request',
    json: async () => ({}),
    text: async () => body,
  } as Response)
  ;(global as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch
  return fetchMock
}

describe('launcher API client', () => {
  afterEach(() => { jest.restoreAllMocks() })

  test('launchApp POSTs to /{run_id}/launch and returns LaunchStatus', async () => {
    const fetchMock = mockFetchOK({ ...idleStatus, state: 'installing', run_id: 'r123' })
    const s = await launchApp('r123')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${BASE}/r123/launch`)
    expect(init.method).toBe('POST')
    expect(s.state).toBe('installing')
    expect(s.run_id).toBe('r123')
  })

  test('stopApp POSTs to /launcher/stop', async () => {
    const fetchMock = mockFetchOK(idleStatus)
    await stopApp()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${BASE}/launcher/stop`)
    expect(init.method).toBe('POST')
  })

  test('getLauncherState GETs /launcher/state', async () => {
    const fetchMock = mockFetchOK(idleStatus)
    const s = await getLauncherState()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).toBe(`${BASE}/launcher/state`)
    expect(init?.method ?? 'GET').toBe('GET')
    expect(s.state).toBe('idle')
  })

  test('launchApp throws with status + body on non-2xx', async () => {
    mockFetchError(404, 'run not found')
    await expect(launchApp('nope')).rejects.toThrow(/404/)
    await expect(launchApp('nope')).rejects.toThrow(/run not found/)
  })

  test('launcher endpoints do NOT collide with /{run_id}/status path', () => {
    // Defensive: any future refactor that moves /launcher/state back under
    // /launch/* would re-introduce the collision with /{run_id}/status.
    // Encoded as a string comparison so it's caught here too.
    const fetchMock = mockFetchOK(idleStatus)
    getLauncherState()
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).not.toMatch(/\/launch\/status$/)
    expect(url).toMatch(/\/launcher\/state$/)
  })
})
