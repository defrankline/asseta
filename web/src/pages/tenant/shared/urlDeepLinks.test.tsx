import { renderHook, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { custodyService } from '../../../api/services/custodyService';
import type { customerPaymentService } from '../../../api/services/financeService';
import { page } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PaymentsTab } from '../finance/payments/PaymentsTab';
import { VariancesTab } from '../finance/cash/VariancesTab';
import { useFocusedRecord } from './useFocusedRecord';

const m = vi.hoisted(() => ({
  variances: vi.fn<typeof custodyService.variances>(),
  payments: vi.fn<typeof customerPaymentService.list>(),
}));
vi.mock('../../../api/services/custodyService', async (original) => ({
  ...(await original<typeof import('../../../api/services/custodyService')>()),
  custodyService: { variances: m.variances },
}));
vi.mock('../../../api/services/financeService', async (original) => ({
  ...(await original<typeof import('../../../api/services/financeService')>()),
  customerPaymentService: { list: m.payments, get: vi.fn() },
}));

beforeEach(() => {
  m.variances.mockReset().mockResolvedValue(page([]));
  m.payments.mockReset().mockResolvedValue(page([]));
});

describe('dashboard links carry their filters to the API', () => {
  it('variances: a period figure and a still-open figure carry their filters', async () => {
    renderWithProviders(<VariancesTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead],
      route: '/?direction=OVERAGE&date_from=2026-11-01&date_to=2026-11-09&open_only=true',
    });
    await waitFor(() => {
      expect(m.variances).toHaveBeenCalled();
    });
    expect(m.variances.mock.calls[0]?.[0].filters).toMatchObject({
      direction: 'OVERAGE',
      date_from: '2026-11-01',
      date_to: '2026-11-09',
      open_only: 'true',
    });
    expect(m.variances.mock.calls[0]?.[0].filters?.status).toBeUndefined();
    expect(screen.getByText('Still open')).toBeInTheDocument();
    expect(screen.queryByText(/every date/)).toBeNull();
  });

  it('variances: direction, all statuses', async () => {
    renderWithProviders(<VariancesTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead],
      route: '/?direction=SHORTAGE',
    });
    await waitFor(() => {
      expect(m.variances).toHaveBeenCalled();
    });
    expect(m.variances.mock.calls[0]?.[0].filters).toMatchObject({ direction: 'SHORTAGE' });
    expect(m.variances.mock.calls[0]?.[0].filters?.status).toBeUndefined();
    expect(screen.getByText('Shortages only')).toBeInTheDocument();
  });

  it('payments: status, method and period', async () => {
    renderWithProviders(<PaymentsTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead],
      route: '/?method=CASH&date_from=2026-11-01&date_to=2026-11-09',
    });
    await waitFor(() => {
      expect(m.payments).toHaveBeenCalled();
    });
    expect(m.payments.mock.calls[0]?.[0].filters).toMatchObject({
      method: 'CASH',
      date_from: '2026-11-01',
      date_to: '2026-11-09',
    });
    expect(m.payments.mock.calls[0]?.[0].filters?.status).toBeUndefined();
  });
});

describe('useFocusedRecord', () => {
  it('opens the record by its own id and hands it over', async () => {
    const load = vi.fn().mockResolvedValue({ id: 'z' });
    const onFound = vi.fn();
    const { result } = renderHook(() => useFocusedRecord<{ id: string }>(load, 'z', onFound));
    await waitFor(() => {
      expect(result.current.record).toEqual({ id: 'z' });
    });
    expect(load).toHaveBeenCalledWith('z', expect.any(AbortSignal));
    expect(onFound).toHaveBeenCalledWith({ id: 'z' });
    expect(result.current.missing).toBe(false);
  });

  it('reports a record it cannot open', async () => {
    const load = vi.fn().mockRejectedValue(new Error('404'));
    const { result } = renderHook(() => useFocusedRecord<{ id: string }>(load, 'nope'));
    await waitFor(() => {
      expect(result.current.missing).toBe(true);
    });
  });

  it('does nothing without an id', () => {
    const load = vi.fn();
    const { result } = renderHook(() => useFocusedRecord<{ id: string }>(load, undefined));
    expect(load).not.toHaveBeenCalled();
    expect(result.current).toEqual({ record: null, missing: false });
  });
});
