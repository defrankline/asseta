import { afterEach, describe, expect, it, vi } from 'vitest';
import { registerRequestContext } from '../requestContext';
import { reportService } from './reportService';

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('../client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../client')>();
  return { ...actual, http: { get: mocks.get } };
});

function errorResponse(status: number, code: string) {
  const body = JSON.stringify({
    error: { code, message: 'nope', correlation_id: 'c1', details: [] },
  });
  return { status, data: new Blob([body], { type: 'application/json' }), headers: {} };
}

let restore: () => void = () => undefined;
afterEach(() => {
  restore();
  vi.clearAllMocks();
});

describe('reportService.download', () => {
  it('sends an expired session to sign-in like every other request', async () => {
    const onUnauthorized = vi.fn();
    restore = registerRequestContext({ onUnauthorized });
    mocks.get.mockResolvedValue(errorResponse(401, 'NOT_AUTHENTICATED'));
    await expect(reportService.download('tenant', 'jobs', 'csv', {})).rejects.toMatchObject({
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('reports a lost mandate for the active tenant', async () => {
    const onMandateLost = vi.fn();
    restore = registerRequestContext({ onMandateLost, getActiveTenantId: () => 'tenant-1' });
    mocks.get.mockResolvedValue(errorResponse(403, 'MANDATE_ENDED'));
    await expect(reportService.download('tenant', 'jobs', 'pdf', {})).rejects.toMatchObject({
      code: 'MANDATE_ENDED',
    });
    expect(onMandateLost).toHaveBeenCalledWith('tenant-1', 'MANDATE_ENDED');
  });

  it('does not sign out on other errors', async () => {
    const onUnauthorized = vi.fn();
    restore = registerRequestContext({ onUnauthorized });
    mocks.get.mockResolvedValue(errorResponse(403, 'PERMISSION_DENIED'));
    await expect(reportService.download('tenant', 'jobs', 'csv', {})).rejects.toMatchObject({
      status: 403,
    });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
