import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { engineHoursService } from '../../../api/services/engineHoursService';
import type { meterService } from '../../../api/services/meterService';
import type { policyService } from '../../../api/services/policyService';
import { MACHINE_ID, makeCapture } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ProposeCorrectionDialog } from '../engineHours/ProposeCorrectionDialog';
import { ConsoleCaptureDialog } from './ConsoleCaptureDialog';

const mocks = vi.hoisted(() => ({
  submitCapture: vi.fn<typeof meterService.submitCapture>(),
  upload: vi.fn<typeof meterService.upload>(),
  effective: vi.fn<typeof policyService.effective>(),
  proposeCorrection: vi.fn<typeof engineHoursService.proposeCorrection>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { submitCapture: mocks.submitCapture, upload: mocks.upload },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));
vi.mock('../../../api/services/engineHoursService', () => ({
  engineHoursService: { proposeCorrection: mocks.proposeCorrection },
}));

const PERMS = ['tenant.meter.capture', 'tenant.policy.read'];

beforeEach(() => {
  mocks.effective.mockResolvedValue({
    policy_type: 'METER_CAPTURE',
    version_stamp: 'MC:P1',
    values: { opening_mode: 'AUTOMATIC', closing_mode: 'MANUAL', manual_photo_required: false },
  });
  mocks.submitCapture.mockResolvedValue({
    capture: makeCapture({ job_id: null, kind: 'DAILY' }),
    findings: [],
  });
});

async function fillManual(user: ReturnType<typeof userEvent.setup>, reading: string) {
  await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
  await user.click(await screen.findByRole('option', { name: 'Manual (numeric entry)' }));
  await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), reading);
}

describe('DAILY reading (no job)', () => {
  it('submits the machine instead of a job', async () => {
    const user = userEvent.setup();
    const onRecorded = vi.fn();
    renderWithProviders(
      <ConsoleCaptureDialog
        kind="DAILY"
        variant="field"
        machine={{ id: MACHINE_ID, label: 'EX-01 · Excavator' }}
        onClose={vi.fn()}
        onRecorded={onRecorded}
      />,
      { tenantPermissions: PERMS },
    );
    expect(screen.getByText('Record daily reading · EX-01 · Excavator')).toBeInTheDocument();
    // DAILY readings follow the policy's non-opening mode.
    expect(await screen.findByText('Policy requires Manual for this reading')).toBeInTheDocument();
    await screen.findByText('Location disabled');
    await fillManual(user, '1300.5');
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    await waitFor(() => {
      expect(mocks.submitCapture).toHaveBeenCalledTimes(1);
    });
    expect(mocks.submitCapture.mock.calls[0]?.[0]).toMatchObject({
      kind: 'DAILY',
      job_id: null,
      machine_id: MACHINE_ID,
      reading: '1300.5',
    });
    expect(mocks.effective).toHaveBeenCalledWith(
      'METER_CAPTURE',
      { machine_id: MACHINE_ID, site_id: undefined },
      expect.any(AbortSignal),
    );
    expect(onRecorded).toHaveBeenCalled();
  });

  it('asks for the machine when none is given', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <ConsoleCaptureDialog kind="DAILY" variant="field" onClose={vi.fn()} onRecorded={vi.fn()} />,
      { tenantPermissions: PERMS },
    );
    await screen.findByText('Location disabled');
    expect(screen.getByRole('combobox', { name: /Machine/ })).toBeInTheDocument();
    await fillManual(user, '10');
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    expect(await screen.findByText('Choose the machine')).toBeInTheDocument();
    expect(mocks.submitCapture).not.toHaveBeenCalled();
  });
});

describe('ProposeCorrectionDialog', () => {
  it('proposes a same-kind replacement with a reason and keeps the original capture time', async () => {
    const user = userEvent.setup();
    const original = makeCapture({ job_id: null, kind: 'DAILY', reading: '1300.5' });
    mocks.proposeCorrection.mockRejectedValueOnce(new Error('x')).mockResolvedValue({
      id: '99999999-0000-4000-8000-000000000001',
      machine_id: MACHINE_ID,
      job_id: null,
      superseded_capture_id: original.id,
      replacement_capture_id: '99999999-0000-4000-8000-000000000002',
      old_reading: '1300.5',
      new_reading: '1030.5',
      reason: 'Digits swapped when typing',
      status: 'PROPOSED',
      proposed_by: null,
      proposed_at: '2026-10-22T08:00:00Z',
      decided_by: null,
      decided_at: null,
      decision_note: null,
      policy_version: 'EH:P1',
    });
    const onProposed = vi.fn();
    renderWithProviders(
      <ProposeCorrectionDialog
        capture={original}
        machineLabel="EX-01 · Excavator"
        onClose={vi.fn()}
        onProposed={onProposed}
      />,
      { tenantPermissions: PERMS },
    );
    const dialog = await screen.findByRole('dialog');
    await screen.findByText('Location disabled');
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), 'Too short');
    await fillManual(user, '1030.5');
    await user.click(within(dialog).getByRole('button', { name: 'Propose correction' }));
    expect(await screen.findByText('At least 10 characters')).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: /Reason/ }), ' — swapped');
    await user.click(within(dialog).getByRole('button', { name: 'Propose correction' }));
    await user.click(within(dialog).getByRole('button', { name: 'Propose correction' }));
    await waitFor(() => {
      expect(onProposed).toHaveBeenCalled();
    });
    const [first, second] = mocks.proposeCorrection.mock.calls;
    expect(first?.[0]).toMatchObject({
      superseded_capture_id: original.id,
      reason: 'Too short — swapped',
      replacement: {
        kind: 'DAILY',
        job_id: null,
        machine_id: MACHINE_ID,
        reading: '1030.5',
        captured_at: original.captured_at,
      },
    });
    // Retries reuse the same replacement id (no second proposal).
    expect(second?.[0].replacement.id).toBe(first?.[0].replacement.id);
  });
});
