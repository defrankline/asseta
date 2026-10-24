import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { jobService } from '../../../api/services/jobService';
import type { JobStatus } from '../../../api/types';
import { makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { JobActions } from './JobActions';

const mocks = vi.hoisted(() => ({ transition: vi.fn<typeof jobService.transition>() }));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { transition: mocks.transition },
}));

const ALL = ['tenant.job.read', 'tenant.job.write', 'tenant.job.approve', 'tenant.job.log'];

function render(status: JobStatus, perms: string[], accessState: 'FULL' | 'READ_ONLY' = 'FULL') {
  renderWithProviders(<JobActions job={makeJob({ status })} onChanged={vi.fn()} />, {
    tenantPermissions: perms,
    accessState,
  });
}

const buttons = () => screen.queryAllByRole('button').map((b) => b.textContent);

describe('JobActions', () => {
  it.each<[JobStatus, string[], string[]]>([
    ['DRAFT', ALL, ['Submit for approval', 'Cancel job']],
    ['DRAFT', ['tenant.job.read', 'tenant.job.write'], ['Submit for approval']],
    ['PENDING_APPROVAL', ALL, ['Approve', 'Cancel job']],
    ['PENDING_APPROVAL', ['tenant.job.read', 'tenant.job.write', 'tenant.job.log'], []],
    ['APPROVED', ALL, ['Start job', 'Cancel job']],
    ['APPROVED', ['tenant.job.read', 'tenant.job.log'], ['Start job']],
    ['IN_PROGRESS', ALL, ['Complete job']],
    ['IN_PROGRESS', ['tenant.job.read', 'tenant.job.approve'], []],
    ['COMPLETED', ALL, []],
    ['CANCELLED', ALL, []],
  ])('status %s with %j shows %j', (status, perms, expected) => {
    render(status, perms);
    expect(buttons()).toEqual(expected);
  });

  it('shows no actions while the tenant is read-only', () => {
    render('APPROVED', ALL, 'READ_ONLY');
    expect(buttons()).toEqual([]);
  });

  it.each([
    ['START', 'APPROVED', 'Start job', 'OPENING_REQUIRED', /Record the opening meter reading/],
    ['COMPLETE', 'IN_PROGRESS', 'Complete job', 'CLOSING_REQUIRED', /closing meter reading/],
    ['COMPLETE', 'IN_PROGRESS', 'Complete job', 'ACK_REQUIRED', /customer acknowledgement/],
    [
      'APPROVE',
      'PENDING_APPROVAL',
      'Approve',
      'MACHINE_BUSY',
      /already has an approved or running/,
    ],
    ['SUBMIT', 'DRAFT', 'Submit for approval', 'INVALID_JOB_TRANSITION', /reload/],
  ] as const)(
    '%s surfaces %s with its code and hint',
    async (action, status, label, code, hint) => {
      const user = userEvent.setup();
      mocks.transition.mockRejectedValue(
        new ApiError({ status: 422, code, message: 'Rejected by server', correlationId: 'corr-9' }),
      );
      render(status, ALL);
      await user.click(screen.getByRole('button', { name: label }));
      const dialog = await screen.findByRole('dialog');
      await user.click(screen.getAllByRole('button', { name: label }).at(-1) ?? dialog);
      const error = await screen.findByText(new RegExp(`^${code}: Rejected by server`));
      expect(error.textContent).toMatch(hint);
      expect(mocks.transition.mock.calls[0]?.[1]).toEqual({ action, reason: null });
    },
  );

  it('requires a reason to cancel', async () => {
    const user = userEvent.setup();
    mocks.transition.mockResolvedValue(makeJob({ status: 'CANCELLED' }));
    render('DRAFT', ALL);
    await user.click(screen.getByRole('button', { name: 'Cancel job' }));
    await screen.findByRole('dialog');
    const confirm = screen.getAllByRole('button', { name: 'Cancel job' }).at(-1);
    if (confirm === undefined) throw new Error('missing confirm');
    await user.click(confirm);
    expect(await screen.findByText('A reason is required')).toBeInTheDocument();
    expect(mocks.transition).not.toHaveBeenCalled();
    await user.type(screen.getByRole('textbox', { name: /Reason/ }), 'Customer postponed');
    await user.click(confirm);
    await waitFor(() => {
      expect(mocks.transition.mock.calls[0]?.[1]).toEqual({
        action: 'CANCEL',
        reason: 'Customer postponed',
      });
    });
  });

  describe('a job requested from the field', () => {
    const requested = (overrides: Parameters<typeof makeJob>[0] = {}) =>
      makeJob({
        status: 'PENDING_APPROVAL',
        supervisor_id: 'ffffffff-0000-4000-8000-000000000001',
        requested_by_staff_id: 'ffffffff-0000-4000-8000-000000000001',
        requested_by_name: 'Asha Mwita',
        request_note: 'Dig a trench at the north gate',
        rate_source: 'PENDING_PRICE',
        hourly_rate: '0.0000',
        ...overrides,
      });

    it('shows who requested it and requires the hourly rate when there is no price yet', async () => {
      const user = userEvent.setup();
      mocks.transition.mockResolvedValue(requested({ status: 'APPROVED' }));
      renderWithProviders(<JobActions job={requested()} onChanged={vi.fn()} />, {
        tenantPermissions: ALL,
      });
      expect(buttons()).toEqual(['Approve', 'Decline request']);
      await user.click(screen.getByRole('button', { name: 'Approve' }));
      const dialog = await screen.findByRole('dialog');
      expect(within(dialog).getByText('Requested from the field by Asha Mwita')).toBeVisible();
      expect(within(dialog).getByText('Dig a trench at the north gate')).toBeVisible();
      await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
      expect(await within(dialog).findByText('Hourly rate is required')).toBeInTheDocument();
      expect(mocks.transition).not.toHaveBeenCalled();
      await user.type(within(dialog).getByRole('textbox', { name: /Hourly rate/ }), '120000');
      await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
      await waitFor(() => {
        expect(mocks.transition.mock.calls[0]?.[1]).toEqual({
          action: 'APPROVE',
          reason: null,
          hourly_rate: '120000',
        });
      });
    });

    it('explains PRICE_REQUIRED', async () => {
      const user = userEvent.setup();
      mocks.transition.mockRejectedValue(
        new ApiError({
          status: 422,
          code: 'PRICE_REQUIRED',
          message: 'No price',
          correlationId: null,
        }),
      );
      renderWithProviders(
        <JobActions job={requested({ rate_source: 'RATE_CARD:abc' })} onChanged={vi.fn()} />,
        { tenantPermissions: ALL },
      );
      await user.click(screen.getByRole('button', { name: 'Approve' }));
      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
      const error = await screen.findByText(/^PRICE_REQUIRED: No price/);
      expect(error.textContent).toMatch(/enter the hourly rate/);
    });

    it('sends a changed price with APPROVE, never an unchanged one', async () => {
      const user = userEvent.setup();
      mocks.transition.mockResolvedValue(requested({ status: 'APPROVED' }));
      renderWithProviders(
        <JobActions
          job={requested({ rate_source: 'RATE_CARD:abc', hourly_rate: '100000.0000' })}
          onChanged={vi.fn()}
        />,
        { tenantPermissions: ALL },
      );
      await user.click(screen.getByRole('button', { name: 'Approve' }));
      const dialog = await screen.findByRole('dialog');
      const rate = within(dialog).getByRole('textbox', { name: /Hourly rate/ });
      expect(rate).toHaveValue('100000.0000');
      await user.clear(rate);
      await user.type(rate, '110000');
      await user.click(within(dialog).getByRole('button', { name: 'Approve' }));
      await waitFor(() => {
        expect(mocks.transition.mock.calls[0]?.[1]).toEqual({
          action: 'APPROVE',
          reason: null,
          hourly_rate: '110000',
        });
      });
    });

    it('declines with a reason (CANCEL)', async () => {
      const user = userEvent.setup();
      mocks.transition.mockResolvedValue(requested({ status: 'CANCELLED' }));
      renderWithProviders(<JobActions job={requested()} onChanged={vi.fn()} />, {
        tenantPermissions: ALL,
      });
      await user.click(screen.getByRole('button', { name: 'Decline request' }));
      const dialog = await screen.findByRole('dialog');
      expect(within(dialog).getByText(/The supervisor is told your reason/)).toBeVisible();
      await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Machine booked');
      await user.click(within(dialog).getByRole('button', { name: 'Decline request' }));
      await waitFor(() => {
        expect(mocks.transition.mock.calls[0]?.[1]).toEqual({
          action: 'CANCEL',
          reason: 'Machine booked',
        });
      });
    });
  });
});
