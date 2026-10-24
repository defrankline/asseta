import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { accountabilityService } from '../../../api/services/accountabilityService';
import type { AccountabilitySummaryDto, SyncConflictDto } from '../../../api/custodyTypes';
import { ME, OTHER_USER, page, STAFF_ID } from '../../../test/financeFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AccountabilityPage } from './AccountabilityPage';
import { SecurityEventsPage } from './SecurityEventsPage';
import { SyncConflictsPage } from './SyncConflictsPage';

const m = vi.hoisted(() => ({
  summary: vi.fn<typeof accountabilityService.summary>(),
  securityEvents: vi.fn<typeof accountabilityService.securityEvents>(),
  syncConflicts: vi.fn<typeof accountabilityService.syncConflicts>(),
  syncConflict: vi.fn<typeof accountabilityService.syncConflict>(),
  resolveSyncConflict: vi.fn<typeof accountabilityService.resolveSyncConflict>(),
}));
vi.mock('../../../api/services/accountabilityService', () => ({ accountabilityService: m }));

function summary(o: Partial<AccountabilitySummaryDto> = {}): AccountabilitySummaryDto {
  return {
    as_of: '2026-10-21T12:00:00Z',
    policy_version: 'v1',
    hidden_tiles: ['payments'],
    unavailable_tiles: ['engine_hours'],
    customer_hours: null,
    hours_awaiting_activation: null,
    engine_hours: null,
    unexplained_hours: null,
    missing_daily_reports: null,
    investigations: { open: 2, in_review: 1 },
    cash: {
      custodians: [
        {
          staff_member_id: STAFF_ID,
          staff_name: 'Sam Supervisor',
          currency: 'TZS',
          outstanding: '250000.0000',
          in_transit_out: '0.0000',
          claimed_unverified_handovers: '0.0000',
          pending_floats: '0.0000',
        },
      ],
      transfers_awaiting_acknowledgement: [{ currency: 'TZS', count: 3, amount: '45000.0000' }],
      floats_awaiting_acknowledgement: [],
      remittances_awaiting_confirmation: [],
      partial_remittances_in_window: 1,
    },
    payments: null,
    discrepancies: {
      open_variances: [{ currency: 'TZS', count: 2, amount: '10000.0000' }],
      write_offs_proposed: 1,
      sync_conflicts_unresolved: 4,
    },
    unauthorized_attempts: { window_days: 7, permission_denied: 5, segregation_of_duties: 2 },
    outstanding_approvals: {
      approval_requests: 1,
      cash_retentions: 2,
      custody_adjustments: 0,
      write_offs: 1,
      payments_to_verify: 0,
      remittances_to_verify: 0,
      total: 4,
    },
    ...o,
  };
}

function conflict(o: Partial<SyncConflictDto> = {}): SyncConflictDto {
  return {
    operation_id: 'oooooooo-0000-4000-8000-000000000001',
    op_type: 'CASH_TRANSFER',
    status: 'CONFLICT',
    error_code: 'TRANSFER_SAME_CUSTODIAN',
    error_message: 'Sender and receiver must differ',
    server_state: {},
    payload: { amount: '5000' },
    created_at_device: '2026-10-21T07:00:00Z',
    received_at: '2026-10-21T08:00:00Z',
    attempts: 1,
    device_id: 'dev-1',
    device_platform: 'ANDROID',
    submitted_by: OTHER_USER,
    submitted_by_name: 'Field Recorder',
    resolution: null,
    ...o,
  };
}

beforeEach(() => {
  m.summary.mockResolvedValue(summary());
});

describe('AccountabilityPage', () => {
  it('shows the returned tiles, notes hidden ones and links each figure to its list', async () => {
    renderWithProviders(<AccountabilityPage />, {
      tenantPermissions: [
        P.tenantAccountabilityRead,
        P.tenantFinanceRead,
        P.tenantSecurityEventRead,
        P.tenantSyncConflictRead,
        P.tenantCaseRead,
      ],
    });
    const cash = await screen.findByRole('article', { name: 'Cash per custodian' });
    expect(within(cash).getByRole('link', { name: /Sam Supervisor/ })).toHaveAttribute(
      'href',
      `/tenant/finance/cash?tab=custody&staff_member_id=${STAFF_ID}`,
    );
    const pending = screen.getByRole('article', {
      name: 'Cash awaiting acknowledgement or confirmation',
    });
    expect(within(pending).getByRole('link', { name: /Transfers: 3 in TZS/ })).toHaveAttribute(
      'href',
      '/tenant/finance/cash?tab=transfers&status=PENDING_ACKNOWLEDGEMENT',
    );
    const attempts = screen.getByRole('article', { name: 'Refused attempts' });
    expect(within(attempts).getByRole('link', { name: /Missing permission: 5/ })).toHaveAttribute(
      'href',
      '/tenant/security-events?kind=PERMISSION_DENIED',
    );
    const discrepancies = screen.getByRole('article', { name: 'Open discrepancies' });
    expect(
      within(discrepancies).getByRole('link', { name: /Offline operations to review: 4/ }),
    ).toHaveAttribute('href', '/tenant/sync-conflicts');
    expect(screen.queryByRole('article', { name: 'Payments awaiting confirmation' })).toBeNull();
    expect(
      screen.getByText(
        /Hidden by your organisation’s oversight policy: Payments awaiting confirmation/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Not available yet: Engine-hour reconciliation/)).toBeInTheDocument();
  });

  it('shows figures without links when the viewer may not open the list', async () => {
    renderWithProviders(<AccountabilityPage />, {
      tenantPermissions: [P.tenantAccountabilityRead],
    });
    const attempts = await screen.findByRole('article', { name: 'Refused attempts' });
    expect(within(attempts).queryByRole('link')).toBeNull();
    expect(within(attempts).getByText('Missing permission')).toBeInTheDocument();
  });
});

describe('SecurityEventsPage', () => {
  it('filters by the kind in the URL', async () => {
    m.securityEvents.mockResolvedValue(
      page([
        {
          id: 'e1',
          occurred_at: '2026-10-21T08:00:00Z',
          kind: 'SEGREGATION_OF_DUTIES',
          actor_user_id: OTHER_USER,
          actor_subject: null,
          actor_display_name: 'Asha Accountant',
          permission: null,
          action: 'decideCashRetention',
          entity_type: 'cash_retention',
          entity_id: 'r1',
          request_method: 'POST',
          request_path: '/api/v1/tenant/cash/retentions/r1/decision',
          detail: {},
        },
      ]),
    );
    renderWithProviders(<SecurityEventsPage />, {
      tenantPermissions: [P.tenantSecurityEventRead],
      route: '/tenant/security-events?kind=SEGREGATION_OF_DUTIES',
    });
    expect(await screen.findByText('Asha Accountant')).toBeInTheDocument();
    expect(m.securityEvents).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ kind: 'SEGREGATION_OF_DUTIES' }) as unknown,
      }),
      expect.any(AbortSignal),
    );
  });
});

describe('SyncConflictsPage', () => {
  it('records a dismissal with a reason', async () => {
    const user = userEvent.setup();
    m.syncConflicts.mockResolvedValue(page([conflict()]));
    m.resolveSyncConflict.mockResolvedValue(conflict());
    renderWithProviders(<SyncConflictsPage />, {
      tenantPermissions: [P.tenantSyncConflictRead, P.tenantSyncConflictResolve],
    });
    await user.click(
      await screen.findByRole('button', { name: 'Actions for operation Cash transfer' }),
    );
    await user.click(screen.getByRole('menuitem', { name: 'Resolve' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: /Outcome/ }));
    await user.click(await screen.findByRole('option', { name: /Dismiss/ }));
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Duplicate entry');
    await user.click(within(dialog).getByRole('button', { name: 'Record outcome' }));
    await waitFor(() => {
      expect(m.resolveSyncConflict).toHaveBeenCalledWith(
        conflict().operation_id,
        {
          outcome: 'DISMISSED',
          reason: 'Duplicate entry',
          recaptured_entity_type: null,
          recaptured_entity_id: null,
        },
        expect.any(String),
      );
    });
    expect(m.syncConflicts).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ resolved: 'false' }) as unknown,
      }),
      expect.any(AbortSignal),
    );
  });

  it('does not let the submitter resolve their own operation', async () => {
    const user = userEvent.setup();
    m.syncConflicts.mockResolvedValue(page([conflict({ submitted_by: ME })]));
    renderWithProviders(<SyncConflictsPage />, {
      tenantPermissions: [P.tenantSyncConflictRead, P.tenantSyncConflictResolve],
    });
    await user.click(
      await screen.findByRole('button', { name: 'Actions for operation Cash transfer' }),
    );
    expect(screen.getByRole('menuitem', { name: /not allowed: you submitted it/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });
});
