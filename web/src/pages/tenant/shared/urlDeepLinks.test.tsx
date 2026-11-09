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
  const rows = [{ id: 'a' }, { id: 'b' }];
  it('finds a record on a later page', async () => {
    const fetchList = vi
      .fn()
      .mockResolvedValueOnce({ items: rows, total: 400, page: 1, page_size: 200 })
      .mockResolvedValueOnce({ items: [{ id: 'z' }], total: 400, page: 2, page_size: 200 });
    const { result } = renderHook(() => useFocusedRecord<{ id: string }>(fetchList, 'z'));
    await waitFor(() => {
      expect(result.current.record).toEqual({ id: 'z' });
    });
  });

  it('reports a record it cannot find', async () => {
    const fetchList = vi.fn().mockResolvedValue({ items: rows, total: 2, page: 1, page_size: 200 });
    const { result } = renderHook(() => useFocusedRecord<{ id: string }>(fetchList, 'nope'));
    await waitFor(() => {
      expect(result.current.missing).toBe(true);
    });
  });
});
