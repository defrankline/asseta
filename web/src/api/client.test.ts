import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type InternalAxiosRequestConfig,
} from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './ApiError';
import { createApiClient, createHttpClient, HEADER, toListParams } from './client';
import type { RequestContext } from './requestContext';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const TENANT = '11111111-1111-4111-8111-111111111111';

function setup(
  opts: { tenantId?: string | null; respond?: (c: InternalAxiosRequestConfig) => unknown } = {},
) {
  const seen: InternalAxiosRequestConfig[] = [];
  const ctx: RequestContext = {
    getAccessToken: vi.fn(() => Promise.resolve('tok-123')),
    getActiveTenantId: () => (opts.tenantId === undefined ? TENANT : opts.tenantId),
    onUnauthorized: vi.fn(),
    refreshAccessToken: vi.fn(() => Promise.resolve()),
    onMandateLost: vi.fn(),
  };
  const instance = createHttpClient('/api/v1', ctx);
  const adapter: AxiosAdapter = (config) => {
    seen.push(config);
    const body = opts.respond ? opts.respond(config) : { ok: true };
    return Promise.resolve({ data: body, status: 200, statusText: 'OK', headers: {}, config });
  };
  instance.defaults.adapter = adapter;
  return { api: createApiClient(instance), instance, ctx, seen };
}

function failWith(status: number, data: unknown): AxiosAdapter {
  return (config) =>
    Promise.reject(
      new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, {
        data,
        status,
        statusText: 'ERR',
        headers: new AxiosHeaders(),
        config,
      }),
    );
}

const header = (c: InternalAxiosRequestConfig | undefined, name: string) => c?.headers.get(name);

describe('http client request interceptor', () => {
  it('adds bearer token and a fresh v4 correlation id per request', async () => {
    const { api, seen } = setup();
    await api.get('/me');
    await api.get('/me');
    expect(header(seen[0], HEADER.authorization)).toBe('Bearer tok-123');
    const c1 = header(seen[0], HEADER.correlation);
    const c2 = header(seen[1], HEADER.correlation);
    expect(c1).toMatch(UUID_V4);
    expect(c2).toMatch(UUID_V4);
    expect(c1).not.toBe(c2);
    expect(header(seen[0], HEADER.tenant)).toBeUndefined();
    expect(header(seen[0], HEADER.idempotency)).toBeUndefined();
  });

  it('adds X-Tenant-ID only for tenant-scoped calls', async () => {
    const { api, seen } = setup();
    await api.get('/machines', { tenantScoped: true });
    expect(header(seen[0], HEADER.tenant)).toBe(TENANT);
  });

  it('rejects tenant-scoped calls when no tenant is selected', async () => {
    const { api, seen } = setup({ tenantId: null });
    await expect(api.get('/machines', { tenantScoped: true })).rejects.toMatchObject({
      code: 'tenant_not_selected',
    });
    expect(seen).toHaveLength(0);
  });

  it('sends Idempotency-Key on mutations and requires it', async () => {
    const { api, instance, seen } = setup();
    await api.post('/things', { a: 1 }, { idempotencyKey: 'key-1' });
    expect(header(seen[0], HEADER.idempotency)).toBe('key-1');
    await expect(instance.post('/things', {})).rejects.toMatchObject({
      code: 'idempotency_key_required',
    });
  });

  it('omits Authorization when there is no token', async () => {
    const { api, ctx, seen } = setup();
    vi.mocked(ctx.getAccessToken).mockResolvedValueOnce(null);
    await api.get('/public');
    expect(header(seen[0], HEADER.authorization)).toBeUndefined();
  });
});

describe('http client error parsing', () => {
  it('parses the error envelope into a typed ApiError', async () => {
    const { api, instance } = setup();
    instance.defaults.adapter = failWith(422, {
      error: {
        code: 'validation_error',
        message: 'Invalid input',
        correlation_id: 'corr-1',
        details: [
          { field: 'name', issue: 'required' },
          { field: null, issue: 'general' },
        ],
      },
    });
    const err = await api.get('/x').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBe(422);
    expect(apiErr.code).toBe('validation_error');
    expect(apiErr.message).toBe('Invalid input');
    expect(apiErr.correlationId).toBe('corr-1');
    expect(apiErr.fieldErrors()).toEqual({ name: 'required' });
  });

  it('falls back to unexpected_response for non-envelope bodies', async () => {
    const { api, instance } = setup();
    instance.defaults.adapter = failWith(500, '<html>oops</html>');
    await expect(api.get('/x')).rejects.toMatchObject({ code: 'unexpected_response', status: 500 });
  });

  it('triggers re-login on 401', async () => {
    const { api, instance, ctx } = setup();
    instance.defaults.adapter = failWith(401, {
      error: { code: 'unauthenticated', message: 'Login', correlation_id: 'c', details: [] },
    });
    await expect(api.get('/me')).rejects.toMatchObject({ status: 401 });
    expect(ctx.onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not trigger re-login on 403', async () => {
    const { api, instance, ctx } = setup();
    instance.defaults.adapter = failWith(403, {
      error: { code: 'forbidden', message: 'No', correlation_id: 'c', details: [] },
    });
    await expect(api.get('/x')).rejects.toMatchObject({ status: 403, code: 'forbidden' });
    expect(ctx.onUnauthorized).not.toHaveBeenCalled();
    expect(ctx.onMandateLost).not.toHaveBeenCalled();
  });

  it.each(['MANDATE_ENDED', 'MANDATE_REQUIRED'])(
    'reports %s with the refused tenant so the session can leave it',
    async (code) => {
      const { api, instance, ctx } = setup();
      instance.defaults.adapter = failWith(403, {
        error: { code, message: 'Mandate not in force', correlation_id: 'c', details: [] },
      });
      await expect(api.get('/tenant/machines', { tenantScoped: true })).rejects.toMatchObject({
        code,
      });
      expect(ctx.onMandateLost).toHaveBeenCalledWith(TENANT, code);
      expect(ctx.onUnauthorized).not.toHaveBeenCalled();
    },
  );

  it('maps network failures to network_error', async () => {
    const { api, instance } = setup();
    instance.defaults.adapter = (config) =>
      Promise.reject(new AxiosError('Network Error', 'ERR_NETWORK', config));
    await expect(api.get('/x')).rejects.toMatchObject({ code: 'network_error', status: null });
  });
});

describe('toListParams', () => {
  it('drops empty values and trims search', () => {
    expect(
      toListParams({
        page: 2,
        page_size: 25,
        sort: '-created_at',
        q: '  cat ',
        filters: { status: '', type: 'x' },
      }),
    ).toEqual({ page: 2, page_size: 25, sort: '-created_at', q: 'cat', type: 'x' });
  });
});
