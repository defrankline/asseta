import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { jobService } from '../../../api/services/jobService';
import type { meterService } from '../../../api/services/meterService';
import { MACHINE_ID, ME_ID, makeAck, makeJob, makeReset } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AcknowledgementTab } from './AcknowledgementTab';
import { MeterResetsTab, OWN_RESET_TEXT } from './MeterResetsTab';

const mocks = vi.hoisted(() => ({
  listResets: vi.fn<typeof meterService.listResets>(),
  attachmentUrl: vi.fn<typeof meterService.attachmentUrl>(),
  listAcks: vi.fn<typeof jobService.listAcknowledgements>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { listResets: mocks.listResets, attachmentUrl: mocks.attachmentUrl },
}));
vi.mock('../../../api/services/jobService', () => ({
  jobService: { listAcknowledgements: mocks.listAcks },
}));

beforeEach(() => {
  mocks.attachmentUrl.mockResolvedValue({
    url: 'https://files.test/e.jpg',
    expires_in_seconds: 300,
  });
  mocks.listResets.mockResolvedValue([
    makeReset({ evidence_attachment_id: '12121212-0000-4000-8000-000000000001' }),
    makeReset({
      id: '77777777-0000-4000-8000-000000000002',
      requested_by: ME_ID,
      reason: 'Mine to approve? No.',
    }),
    makeReset({
      id: '77777777-0000-4000-8000-000000000003',
      status: 'APPROVED',
      reason: 'Earlier rollover',
    }),
  ]);
  mocks.listAcks.mockResolvedValue([makeAck()]);
});

function renderResets(perms: string[]) {
  renderWithProviders(
    <MeterResetsTab machineId={MACHINE_ID} machineName="EX-01 · Excavator" timeZone="UTC" />,
    { tenantPermissions: perms },
  );
}

const rowOf = (text: string) => {
  const row = screen.getByText(text).closest('tr');
  if (row === null) throw new Error(`no row for ${text}`);
  return row;
};

describe('MeterResetsTab', () => {
  it('lists the machine resets from the API and lets approvers pick a pending one', async () => {
    const user = userEvent.setup();
    renderResets(['tenant.meter.read', 'tenant.meter.approve']);
    expect(await screen.findByText('Hour meter replaced after failure')).toBeInTheDocument();
    expect(mocks.listResets).toHaveBeenCalledWith({ machine_id: MACHINE_ID }, expect.anything());
    expect(screen.queryByRole('button', { name: /by ID/ })).not.toBeInTheDocument();

    const own = within(rowOf('Mine to approve? No.')).getByRole('button', { name: /Decide/ });
    expect(own).toBeDisabled();
    expect(own).toHaveAccessibleName(`Decide reset (${OWN_RESET_TEXT})`);
    expect(within(rowOf('Earlier rollover')).queryByRole('button')).not.toBeInTheDocument();

    const other = rowOf('Hour meter replaced after failure');
    await user.click(within(other).getByRole('button', { name: 'View evidence' }));
    await waitFor(() => {
      expect(mocks.attachmentUrl).toHaveBeenCalledWith('12121212-0000-4000-8000-000000000001');
    });
    await user.click(within(other).getByRole('button', { name: 'Decide' }));
    const dialog = await screen.findByRole('dialog', { name: 'Decide meter reset' });
    expect(within(dialog).getByText('Hour meter replaced after failure')).toBeInTheDocument();
  });

  it('shows no decide actions without approve permission', async () => {
    renderResets(['tenant.meter.read', 'tenant.meter.capture']);
    await screen.findByText('Hour meter replaced after failure');
    expect(screen.queryByRole('button', { name: /Decide/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Request meter reset' })).toBeInTheDocument();
  });
});

describe('AcknowledgementTab', () => {
  it('lists acknowledgements from the API and opens the signature on demand', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <AcknowledgementTab
        job={makeJob({ status: 'IN_PROGRESS' })}
        suggestedHours="8.0"
        timeZone="UTC"
        onChanged={vi.fn()}
      />,
      { tenantPermissions: ['tenant.job.read', 'tenant.meter.read'] },
    );
    const card = await screen.findByLabelText('Acknowledgement by Asha Mwita');
    expect(within(card).getByText('Signature image')).toBeInTheDocument();
    expect(within(card).getByText('+255700000001')).toBeInTheDocument();
    expect(within(card).getByText('8.0 h')).toBeInTheDocument();
    expect(mocks.attachmentUrl).not.toHaveBeenCalled();
    await user.click(within(card).getByRole('button', { name: 'View signature' }));
    expect(await within(card).findByRole('img', { name: 'Evidence thumbnail' })).toHaveAttribute(
      'src',
      'https://files.test/e.jpg',
    );
    expect(mocks.attachmentUrl).toHaveBeenCalledWith('55555555-0000-4000-8000-000000000001');
    expect(
      screen.queryByRole('button', { name: 'Record acknowledgement' }),
    ).not.toBeInTheDocument();
  });
});
