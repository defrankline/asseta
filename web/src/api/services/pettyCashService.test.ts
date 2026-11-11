import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  makeFund,
  makeMovement,
  makeStatement,
} from '../../pages/tenant/finance/pettyCash/pettyCashFixtures';
import { varianceSourcePath } from '../../pages/tenant/finance/cash/varianceRecord';
import { pettyCashEntityPath, pettyCashTabPath } from '../../navigation/pettyCashRoutes';
import type { ApiClient } from '../client';
import type { CashVarianceDto } from '../custodyTypes';
import { expenseSchema } from './expenseSchemas';
import { varianceSchema } from './custodySchemas';
import { pettyCashService } from './pettyCashService';
import { parseResponse } from '../validation';
import { makeExpense } from '../../test/financeFixtures';

const api = vi.hoisted(() => ({
  get: vi.fn<ApiClient['get']>(),
  post: vi.fn<ApiClient['post']>(),
  put: vi.fn<ApiClient['put']>(),
  patch: vi.fn<ApiClient['patch']>(),
  delete: vi.fn<ApiClient['delete']>(),
}));
vi.mock('../client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../client')>();
  return { ...actual, apiClient: api };
});

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.put.mockReset();
});

describe('petty cash service', () => {
  it('lists funds with balances under /tenant/petty-cash/funds', async () => {
    api.get.mockResolvedValue({ items: [makeFund()], total: 1, page: 1, page_size: 20 });
    const page = await pettyCashService.funds({ page: 1, page_size: 20, q: 'office' });
    expect(page.items[0]?.balance?.available_to_spend).toBe('300000.0000');
    expect(api.get.mock.calls[0]?.[0]).toBe('/tenant/petty-cash/funds');
    expect(api.get.mock.calls[0]?.[1]).toMatchObject({ tenantScoped: true });
  });

  it('reads a statement for a period', async () => {
    api.get.mockResolvedValue(makeStatement());
    const st = await pettyCashService.statement('fund-1', { from: '2026-11-01', to: undefined });
    expect(st.lines).toHaveLength(2);
    expect(api.get.mock.calls[0]?.[0]).toBe('/tenant/petty-cash/funds/fund-1/statement');
    expect(api.get.mock.calls[0]?.[1]?.params).toEqual({ from: '2026-11-01' });
  });

  it('sends a decision with an idempotency key', async () => {
    api.post.mockResolvedValue(makeMovement({ status: 'APPROVED' }));
    await pettyCashService.decideMovement('mv-1', { approve: true, note: null }, 'key-1');
    expect(api.post).toHaveBeenCalledWith(
      '/tenant/petty-cash/movements/mv-1/decision',
      { approve: true, note: null },
      { tenantScoped: true, idempotencyKey: 'key-1' },
    );
  });

  it('updates a fund with PUT and its version', async () => {
    api.put.mockResolvedValue(makeFund({ version: 3 }));
    const body = { code: 'PC-01', name: 'Office box', approved_limit: '1', version: 2 };
    await pettyCashService.update('fund-1', body, 'k');
    expect(api.put.mock.calls[0]?.[0]).toBe('/tenant/petty-cash/funds/fund-1');
  });
});

describe('petty cash in other records', () => {
  it('parses an expense paid from a fund with its control flags', () => {
    const e = parseResponse(
      expenseSchema,
      {
        ...makeExpense(),
        paid_from: 'PETTY_CASH',
        petty_cash_fund_id: 'fund-1',
        control_flags: ['OVERSPEND'],
      },
      'expense',
    );
    expect(e.paid_from).toBe('PETTY_CASH');
    expect(e.control_flags).toEqual(['OVERSPEND']);
  });

  it('parses a petty cash count variance and links it to the count', () => {
    const base = {
      id: 'v-1',
      source_type: 'PETTY_CASH_COUNT',
      source_id: 'count-1',
      staff_member_id: 'staff-1',
      counterparty_staff_id: null,
      currency: 'TZS',
      declared_amount: '100.0000',
      received_amount: '90.0000',
      amount: '10.0000',
      kind: 'SHORTFALL',
      case_id: null,
      opened_at: '2026-11-10T08:00:00Z',
      opened_by: null,
      status: 'OPEN',
      reason_id: null,
      proposed_by: null,
      proposed_at: null,
      proposal_note: null,
      outcome: null,
      resolved_by: null,
      resolved_at: null,
      resolution_note: null,
      petty_cash_fund_id: 'fund-1',
      petty_cash_fund_name: 'Office box',
    };
    const v: CashVarianceDto = parseResponse(varianceSchema, base, 'variance');
    expect(varianceSourcePath(v)).toBe('/tenant/finance/petty-cash/counts/count-1');
    expect(v.petty_cash_fund_id).toBe('fund-1');
  });

  it('routes ledger lines and tabs', () => {
    expect(pettyCashEntityPath('expense', 'e-1')).toBe('/tenant/expenses/e-1');
    expect(pettyCashEntityPath('petty_cash_adjustment', 'a-1')).toBe(
      '/tenant/finance/petty-cash/adjustments/a-1',
    );
    expect(pettyCashEntityPath('unknown', 'x')).toBeNull();
    expect(pettyCashTabPath('returns', { status: 'CLAIMED', fund_id: undefined })).toBe(
      '/tenant/finance/petty-cash?tab=returns&status=CLAIMED',
    );
  });
});
