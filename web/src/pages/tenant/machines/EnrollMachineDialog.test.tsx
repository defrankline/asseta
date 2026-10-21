import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { tenantBillingService } from '../../../api/services/tenantBillingService';
import type { ChargePreviewDto, EnrollmentResultDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { todayIsoDate } from '../../../utils/dates';
import { EnrollMachineDialog } from './EnrollMachineDialog';
import { makeMachine } from './machineFixtures';

const mocks = vi.hoisted(() => ({
  previewEnrollment: vi.fn<typeof tenantBillingService.previewEnrollment>(),
  enroll: vi.fn<typeof tenantBillingService.enroll>(),
}));
vi.mock('../../../api/services/tenantBillingService', () => ({
  tenantBillingService: { previewEnrollment: mocks.previewEnrollment, enroll: mocks.enroll },
}));

const machine = makeMachine();
const charge: ChargePreviewDto = {
  line_type: 'PRORATION_CHARGE',
  amount: '51612.9032',
  currency: 'TZS',
  days: 16,
  period_days: 31,
  service_from: '2026-10-16',
  service_to: '2026-10-31',
  explanation: '16/31 days at the current rate.',
};

describe('EnrollMachineDialog', () => {
  it('previews the proration, then confirms the identical body with a new key', async () => {
    const user = userEvent.setup();
    mocks.previewEnrollment.mockResolvedValue(charge);
    const body = { machine_id: machine.id, effective_from: todayIsoDate() };
    const result: EnrollmentResultDto = {
      enrollment: {
        id: '99999999-9999-4999-8999-999999999999',
        machine_id: machine.id,
        asset_label: 'EX-01 Excavator 1',
        effective_from: body.effective_from,
        effective_to: null,
        end_reason: null,
      },
      charge,
    };
    mocks.enroll.mockResolvedValue(result);
    const onEnrolled = vi.fn();
    const onClose = vi.fn();
    renderWithProviders(
      <EnrollMachineDialog machine={machine} onClose={onClose} onEnrolled={onEnrolled} />,
      { tenantPermissions: ['tenant.billing.enroll'] },
    );

    expect(screen.queryByRole('button', { name: 'Confirm enrollment' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Preview' }));

    expect(await screen.findByText('TZS 51,612.90')).toBeInTheDocument();
    expect(screen.getByText('16/31 days at the current rate.')).toBeInTheDocument();
    expect(mocks.previewEnrollment).toHaveBeenCalledWith(body, expect.any(String));
    expect(mocks.enroll).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Confirm enrollment' }));
    await waitFor(() => {
      expect(mocks.enroll).toHaveBeenCalledTimes(1);
    });
    const [sent, key] = mocks.enroll.mock.calls[0] ?? [];
    expect(sent).toEqual(body);
    expect(key).not.toBe(mocks.previewEnrollment.mock.calls[0]?.[1]);
    expect(onEnrolled).toHaveBeenCalledWith(result);
    expect(onClose).toHaveBeenCalled();
  });

  it('explains when there is no proration charge', async () => {
    const user = userEvent.setup();
    mocks.previewEnrollment.mockResolvedValue(null);
    renderWithProviders(
      <EnrollMachineDialog machine={machine} onClose={vi.fn()} onEnrolled={vi.fn()} />,
      { tenantPermissions: ['tenant.billing.enroll'] },
    );
    await user.click(screen.getByRole('button', { name: 'Preview' }));
    expect(await screen.findByText('No proration charge')).toBeInTheDocument();
  });
});
