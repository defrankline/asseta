import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { meterService } from '../../../api/services/meterService';
import type { ResetDto } from '../../../api/types';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MACHINE_ID } from '../../../test/jobFixtures';
import { DecideResetDialog } from './DecideResetDialog';

const mocks = vi.hoisted(() => ({ decide: vi.fn<typeof meterService.decideReset>() }));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { decideReset: mocks.decide },
}));

const RESET: ResetDto = {
  id: '77777777-0000-4000-8000-000000000001',
  machine_id: MACHINE_ID,
  old_reading: '9999.9',
  new_reading: '0.0',
  effective_at: '2026-10-21T08:00:00Z',
  reason: 'Hour meter replaced after failure',
  evidence_attachment_id: null,
  status: 'PENDING',
  requested_by: '44444444-4444-4444-8444-444444444444',
  decided_at: null,
};

describe('DecideResetDialog', () => {
  it('shows SEGREGATION_OF_DUTIES clearly when the requester tries to approve', async () => {
    const user = userEvent.setup();
    mocks.decide.mockRejectedValue(
      new ApiError({
        status: 422,
        code: 'SEGREGATION_OF_DUTIES',
        message: 'Requester cannot approve their own reset',
        correlationId: 'corr-7',
      }),
    );
    renderWithProviders(
      <DecideResetDialog reset={RESET} timeZone="UTC" onClose={vi.fn()} onDecided={vi.fn()} />,
      { tenantPermissions: ['tenant.meter.approve'] },
    );
    await user.click(screen.getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: /^Approve reset/ }));
    await user.type(screen.getByRole('textbox', { name: /Note/ }), 'Workshop card attached');
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    const error = await screen.findByText(/^SEGREGATION_OF_DUTIES: Requester cannot approve/);
    expect(error.textContent).toMatch(/Another approver must review it/);
    expect(mocks.decide).toHaveBeenCalledWith(
      RESET.id,
      { outcome: 'EXPLAINED', note: 'Workshop card attached' },
      expect.any(String),
    );
  });

  it('records a rejection for the picked reset', async () => {
    const user = userEvent.setup();
    mocks.decide.mockResolvedValue({ ...RESET, status: 'REJECTED' });
    const onDecided = vi.fn();
    renderWithProviders(
      <DecideResetDialog reset={RESET} timeZone="UTC" onClose={vi.fn()} onDecided={onDecided} />,
      { tenantPermissions: ['tenant.meter.approve'] },
    );
    expect(screen.getByText('Hour meter replaced after failure')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: /Reset ID/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: /Decision/ }));
    await user.click(await screen.findByRole('option', { name: 'Reject reset' }));
    await user.type(screen.getByRole('textbox', { name: /Note/ }), 'No supporting evidence');
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    await waitFor(() => {
      expect(onDecided).toHaveBeenCalled();
    });
    expect(mocks.decide.mock.calls[0]?.[0]).toBe(RESET.id);
    expect(mocks.decide.mock.calls[0]?.[1]).toEqual({
      outcome: 'CONFIRMED',
      note: 'No supporting evidence',
    });
  });
});
