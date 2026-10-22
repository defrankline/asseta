import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../access/permissionCodes';
import type { auditService } from '../../api/services/auditService';
import type { AuditEventDto } from '../../api/types';
import { renderWithProviders } from '../../test/renderWithProviders';
import { diffRows, periodParams } from './auditDisplay';
import { AuditLogPage } from './AuditLogPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof auditService.list>(),
  search: vi.fn(),
  searchTenants: vi.fn(),
}));
vi.mock('../../api/services/auditService', () => ({ auditService: mocks }));
vi.mock('../../api/services/peopleService', () => ({
  PEOPLE_BATCH: 100,
  peopleService: { search: mocks.search, list: vi.fn() },
}));
vi.mock('../platform/shared/platformLookups', () => ({
  searchTenants: mocks.searchTenants,
  tenantLabel: (t: { display_name: string }) => t.display_name,
}));

function event(overrides: Partial<AuditEventDto> = {}): AuditEventDto {
  return {
    id: 'e1',
    occurred_at: '2026-10-21T09:15:00Z',
    tenant_id: 't1',
    actor_user_id: 'u1',
    actor_display_name: 'Neema Mushi',
    actor_roles: ['owner'],
    source: 'WEB',
    device_id: null,
    action: 'finance.invoice.issued',
    entity_type: 'hire_invoice',
    entity_id: 'INV-0042',
    reason: null,
    policy_version: null,
    before: { status: 'DRAFT', total: '100.0000' },
    after: { status: 'ISSUED', total: '100.0000', issued_on: '2026-10-21' },
    correlation_id: 'corr-1',
    mandate_id: null,
    mandate_reference: null,
    ...overrides,
  };
}

const page = (items: AuditEventDto[]) => ({ items, total: items.length, page: 1, page_size: 25 });

beforeEach(() => {
  mocks.list.mockResolvedValue(
    page([
      event(),
      event({
        id: 'e2',
        actor_display_name: 'Asseta Support',
        mandate_reference: 'MSM-2026-0007',
        action: 'jobs.job.updated',
      }),
    ]),
  );
  mocks.search.mockResolvedValue([{ user_id: 'u9', display_name: 'Juma Said' }]);
  mocks.searchTenants.mockResolvedValue([{ id: 't7', display_name: 'Kilimo Hire' }]);
});

const TENANT = { tenantPermissions: [P.tenantAuditRead, P.tenantDirectoryRead] };

describe('AuditLogPage', () => {
  it('shows actor names and the mandate reference for staff actions', async () => {
    renderWithProviders(<AuditLogPage scope="tenant" />, TENANT);
    expect(await screen.findByText('Neema Mushi')).toBeInTheDocument();
    expect(screen.getByText('By Asseta staff under MSM-2026-0007')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith(
      'tenant',
      expect.objectContaining({ page: 1, page_size: 25 }),
      expect.any(AbortSignal),
    );
  });

  it('expands a row into a readable before/after diff', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogPage scope="tenant" />, TENANT);
    const toggle = await screen.findByRole('button', {
      name: 'Show details of finance.invoice.issued',
    });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const diff = screen.getByRole('table', { name: 'Recorded values for finance.invoice.issued' });
    const status = within(diff).getByText('Status').closest('tr');
    expect(status).not.toBeNull();
    expect(within(status as HTMLElement).getByText('DRAFT')).toBeInTheDocument();
    expect(within(status as HTMLElement).getByText('ISSUED')).toBeInTheDocument();
    expect(within(status as HTMLElement).getByText('Changed')).toBeInTheDocument();
    expect(within(diff).getByText('Issued on').closest('tr')).toHaveTextContent('Added');
    expect(screen.getByText('corr-1')).toBeInTheDocument();
  });

  it('sends actor, action prefix, record and period filters to the server', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogPage scope="tenant" />, TENANT);
    await screen.findByText('Neema Mushi');
    await user.click(screen.getByRole('combobox', { name: 'Actor' }));
    await user.click(await screen.findByRole('option', { name: 'Juma Said' }));
    await user.type(screen.getByRole('textbox', { name: 'Action starts with' }), 'finance.');
    await user.type(screen.getByRole('textbox', { name: 'Record type' }), 'hire_invoice');
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(
        'tenant',
        expect.objectContaining({
          filters: expect.objectContaining({
            actor_user_id: 'u9',
            action_prefix: 'finance.',
            entity_type: 'hire_invoice',
          }) as unknown,
        }),
        expect.any(AbortSignal),
      );
    });
  });

  it('does not send an invalid action prefix', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogPage scope="tenant" />, TENANT);
    await screen.findByText('Neema Mushi');
    await user.type(screen.getByRole('textbox', { name: 'Action starts with' }), 'bad prefix!');
    expect(await screen.findByText(/Lowercase letters, digits/)).toBeInTheDocument();
    for (const call of mocks.list.mock.calls) {
      expect(call[1].filters?.action_prefix).toBeUndefined();
    }
  });

  it('filters the platform log by tenant (no people search there)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditLogPage scope="platform" />, { permissions: [P.platformAuditRead] });
    await screen.findByText('Neema Mushi');
    expect(screen.queryByRole('combobox', { name: 'Actor' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Tenant' }));
    await user.click(await screen.findByRole('option', { name: 'Kilimo Hire' }));
    await waitFor(() => {
      expect(mocks.list).toHaveBeenLastCalledWith(
        'platform',
        expect.objectContaining({
          filters: expect.objectContaining({ tenant_id: 't7' }) as unknown,
        }),
        expect.any(AbortSignal),
      );
    });
  });
});

describe('audit helpers', () => {
  it('turns a local period into UTC bounds with an exclusive end', () => {
    expect(periodParams('2026-10-01', '2026-10-31', 'Africa/Dar_es_Salaam')).toEqual({
      occurred_from: '2026-09-30T21:00:00.000Z',
      occurred_to: '2026-10-31T21:00:00.000Z',
    });
    expect(periodParams('', 'nope', 'UTC')).toEqual({});
  });

  it('marks added, removed and changed fields', () => {
    const rows = diffRows({ a: 1, b: true, gone: 'x' }, { a: 2, b: true, added: [1, 2] });
    expect(rows.map((r) => [r.key, r.kind, r.before, r.after])).toEqual([
      ['a', 'changed', '1', '2'],
      ['added', 'added', '—', '1, 2'],
      ['b', 'unchanged', 'Yes', 'Yes'],
      ['gone', 'removed', 'x', '—'],
    ]);
    expect(diffRows(null, { note: 'created' })[0]?.kind).toBe('unchanged');
  });
});
