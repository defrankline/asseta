import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FieldContractDto } from '../../../api/types';
import { makeJob, makeSummary } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { JobSummaryPanel } from '../jobDetail/JobSummaryPanel';
import { ChangeoverReadingDialog } from './ChangeoverReadingDialog';

const m = vi.hoisted(() => ({
  submitCapture: vi.fn(),
  fieldContracts: vi.fn(),
  effective: vi.fn(),
  attemptGpsFix: vi.fn(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { submitCapture: m.submitCapture, upload: vi.fn() },
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { fieldContracts: m.fieldContracts, list: vi.fn() },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: m.effective },
}));
vi.mock('../../../utils/geolocation', () => ({ attemptGpsFix: m.attemptGpsFix }));

const CUSTOMER = 'eeeeeeee-0000-4000-8000-000000000009';
const contract = {
  id: 'cccccccc-0000-4000-8000-000000000009',
  contract_number: 'C-9',
  customer_id: CUSTOMER,
  customer_name: 'Next Customer',
} as unknown as FieldContractDto;

beforeEach(() => {
  vi.clearAllMocks();
  m.fieldContracts.mockResolvedValue([contract]);
  m.effective.mockResolvedValue({ values: {} });
  m.attemptGpsFix.mockResolvedValue({ status: 'UNAVAILABLE' });
  m.submitCapture.mockResolvedValue({ capture: {}, findings: [] });
});

describe('ChangeoverReadingDialog', () => {
  it('requires the next job when the hours after a changeover are billed to it', async () => {
    const user = userEvent.setup();
    m.effective.mockImplementation((type: string) =>
      Promise.resolve({
        values: type === 'ENGINE_HOURS' ? { changeover_splits_billing: true } : {},
      }),
    );
    const job = makeJob({ status: 'IN_PROGRESS' });
    renderWithProviders(
      <ChangeoverReadingDialog job={job} onClose={vi.fn()} onRecorded={vi.fn()} />,
      {
        tenantPermissions: ['tenant.meter.capture'],
      },
    );
    await screen.findByText(/Your company bills the hours after a changeover/);
    await user.click(screen.getByRole('combobox', { name: /Next customer/ }));
    await user.click(await screen.findByRole('option', { name: /Next Customer/ }));
    await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
    await user.click(await screen.findByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1500.5');
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    expect(await screen.findByText('Choose the next job')).toBeInTheDocument();
    expect(m.submitCapture).not.toHaveBeenCalled();
  });

  it('records a DAILY reading on the running job naming the next customer', async () => {
    const user = userEvent.setup();
    const job = makeJob({ status: 'IN_PROGRESS' });
    const onRecorded = vi.fn();
    renderWithProviders(
      <ChangeoverReadingDialog job={job} onClose={vi.fn()} onRecorded={onRecorded} />,
      { tenantPermissions: ['tenant.meter.capture'] },
    );
    await user.click(screen.getByRole('combobox', { name: /Next customer/ }));
    await user.click(await screen.findByRole('option', { name: /Next Customer/ }));
    await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
    await user.click(await screen.findByRole('option', { name: /Manual/ }));
    await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1500.5');
    await waitFor(() => {
      expect(m.attemptGpsFix).toHaveBeenCalled();
    });
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    await waitFor(() => {
      expect(onRecorded).toHaveBeenCalled();
    });
    expect(m.submitCapture.mock.calls[0]?.[0]).toMatchObject({
      job_id: job.id,
      kind: 'DAILY',
      reading: '1500.5',
      changeover_to_customer_id: CUSTOMER,
      changeover_to_job_id: null,
    });
  });
});

describe('JobSummaryPanel', () => {
  const panel = (carried: string) =>
    renderWithProviders(
      <JobSummaryPanel
        summary={makeSummary({ changeover_carried_hours: carried })}
        machineName="EX-01"
        siteName="Quarry"
        timeZone="UTC"
        canSeeExceptions={false}
      />,
      { tenantPermissions: ['tenant.job.read'] },
    );

  it('shows hours carried from a changeover only when there are some', () => {
    const { unmount } = panel('3.00');
    expect(screen.getByText('Hours carried from a changeover')).toBeInTheDocument();
    expect(screen.getByText('3.00 h')).toBeInTheDocument();
    unmount();
    panel('0.00');
    expect(screen.queryByText('Hours carried from a changeover')).not.toBeInTheDocument();
  });
});
