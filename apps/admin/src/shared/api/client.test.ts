import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, type AuthBridge } from './client';
import { ApiRequestError } from './errors';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? '' : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeBridge(initialToken: string | null): AuthBridge & {
  setSessionMock: ReturnType<typeof vi.fn>;
  clearMock: ReturnType<typeof vi.fn>;
  failMock: ReturnType<typeof vi.fn>;
} {
  let token = initialToken;
  const setSessionMock = vi.fn((t: { access_token: string }) => {
    token = t.access_token;
  });
  const clearMock = vi.fn(() => {
    token = null;
  });
  const failMock = vi.fn();
  return {
    getAccessToken: () => token,
    setSession: setSessionMock,
    clearSession: clearMock,
    onAuthFailure: failMock,
    setSessionMock,
    clearMock,
    failMock,
  };
}

describe('ApiClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('attaches Authorization header from the in-memory token', async () => {
    const client = new ApiClient('http://api');
    client.attachAuth(makeBridge('tok-1'));
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await client.request('/me');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe('Bearer tok-1');
    expect(init.credentials).toBe('include');
  });

  it('refreshes once on 401 and retries the original request', async () => {
    const client = new ApiClient('http://api');
    const bridge = makeBridge('expired');
    client.attachAuth(bridge);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'no' } }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'fresh', expires_in: 900 }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'u1' }));

    const result = await client.request<{ id: string }>('/me');

    expect(result).toEqual({ id: 'u1' });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(bridge.setSessionMock).toHaveBeenCalledWith({ access_token: 'fresh', expires_in: 900 });
    expect(fetchMock.mock.calls[1][0]).toBe('http://api/auth/refresh');
  });

  it('clears session and signals auth failure when refresh fails', async () => {
    const client = new ApiClient('http://api');
    const bridge = makeBridge('expired');
    client.attachAuth(bridge);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'no' } }))
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthorized', message: 'no' } }));

    await expect(client.request('/me')).rejects.toBeInstanceOf(ApiRequestError);
    expect(bridge.clearMock).toHaveBeenCalled();
    expect(bridge.failMock).toHaveBeenCalled();
  });

  it('parses API error envelope into ApiRequestError', async () => {
    const client = new ApiClient('http://api');
    client.attachAuth(makeBridge('tok'));
    fetchMock.mockResolvedValueOnce(
      jsonResponse(429, { error: { code: 'rate_limited', message: 'too many' } }),
    );

    await expect(
      client.request('/auth/login', { method: 'POST', skipAuthRefresh: true }),
    ).rejects.toMatchObject({ status: 429, code: 'rate_limited', message: 'too many' });
  });
});
