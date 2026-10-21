import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { subscriptionService } from '../../../api/services/subscriptionService';
import type { ChargePreviewDto, EnrollmentResultDto } from '../../../api/types';
import { ENROLLMENT, SUB_ID } from '../../../test/billingFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { todayIsoDate } from '../../../utils/dates';
import { EndEnrollmentDialog } from './EndEnrollmentDialog';

const mocks = vi.hoisted(() => ({
  previewEndEnrollment: vi.fn<typeof subscriptionService.previewEndEnrollment>(),
  endEnrollment: vi.fn<typeof subscriptionService.endEnrollment>(),
}));
const preview = mocks.previewEndEnrollment;
const end = mocks.endEnrollment;
vi.mock('../../../api/services/subscriptionService', () => ({
  subscriptionService: {
    previewEndEnrollment: mocks.previewEndEnrollment,
    endEnrollment: mocks.endEnrollment,
  },
}));

const charge: ChargePreviewDto = {
  line_type: 'PRORATION_CREDIT',
  amount: '-48387.0968',
  currency: 'TZS',
  days: 15,
  period_days: 31,
  service_from: '2026-10-17',
  service_to: '2026-10-31',
  explanation: '15/31 days credited at the current rate.',
};

describe('EndEnrollmentDialog', () => {
  it('previews the proration effect, then confirms exactly the previewed request', async () => {
    const user = userEvent.setup();
    preview.mockResolvedValue(charge);
    const result: EnrollmentResultDto = {
      enrollment: { ...ENROLLMENT, effective_to: todayIsoDate(), end_reason: 'DISPOSED' },
      charge,
    };
    end.mockResolvedValue(result);
    const onEnded = vi.fn();
    const onClose = vi.fn();
    renderWithProviders(
      <EndEnrollmentDialog
        subscriptionId={SUB_ID}
        enrollment={ENROLLMENT}
        onClose={onClose}
        onEnded={onEnded}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Confirm end' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /^Reason/ }));
    await user.click(await screen.findByRole('option', { name: 'Disposed' }));
    await user.click(screen.getByRole('button', { name: 'Preview' }));

    expect(await screen.findByText('-TZS 48,387.10')).toBeInTheDocument();
    expect(screen.getByText('15/31 days credited at the current rate.')).toBeInTheDocument();
    expect(end).not.toHaveBeenCalled();
    const body = { effective_to: todayIsoDate(), reason: 'DISPOSED' };
    expect(preview).toHaveBeenCalledWith(SUB_ID, ENROLLMENT.id, body, expect.any(String));

    await user.click(screen.getByRole('button', { name: 'Confirm end' }));
    await waitFor(() => {
      expect(end).toHaveBeenCalledTimes(1);
    });
    const [sid, eid, sent, key] = end.mock.calls[0] ?? [];
    expect([sid, eid, sent]).toEqual([SUB_ID, ENROLLMENT.id, body]);
    // The confirm uses its own idempotency key, distinct from the preview call.
    expect(key).not.toBe(preview.mock.calls[0]?.[3]);
    expect(onEnded).toHaveBeenCalledWith(result);
    expect(onClose).toHaveBeenCalled();
  });

  it('explains when ending has no proration effect', async () => {
    const user = userEvent.setup();
    preview.mockResolvedValue(null);
    renderWithProviders(
      <EndEnrollmentDialog
        subscriptionId={SUB_ID}
        enrollment={ENROLLMENT}
        onClose={vi.fn()}
        onEnded={vi.fn()}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Preview' }));
    expect(await screen.findByText('No proration effect')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByRole('button', { name: 'Preview' })).toBeInTheDocument();
  });
});
