import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { alertService } from '../../../api/services/alertService';
import type { AlertDto } from '../../../api/types';
import { lastMap } from '../../../test/maplibreMock';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { AlertDetailDialog } from './AlertDetailDialog';

vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));
const mocks = vi.hoisted(() => ({ act: vi.fn<typeof alertService.act>() }));
vi.mock('../../../api/services/alertService', () => ({ alertService: { act: mocks.act } }));

const ALERT: AlertDto = {
  id: 'a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1',
  machine_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  tracker_id: null,
  alert_type: 'GEOFENCE_EXIT',
  severity: 'WARNING',
  status: 'OPEN',
  event_time: '2026-10-21T08:00:00Z',
  title: 'EX-01 left Site A',
  evidence: { lat: -6.8, lon: 39.2, distance_outside_m: 42.5, geofence_id: 'g-1' },
  policy_version: 'TRACKING:t3',
  created_at: '2026-10-21T08:00:05Z',
  acknowledged_at: null,
  resolved_at: null,
  resolution_note: null,
};

function renderDialog(alert: AlertDto, permissions: string[]) {
  const onChanged = vi.fn();
  renderWithProviders(
    <AlertDetailDialog
      alert={alert}
      machineLabel="EX-01 · Excavator"
      timeZone="UTC"
      onClose={vi.fn()}
      onChanged={onChanged}
    />,
    { tenantPermissions: permissions },
  );
  return onChanged;
}

describe('AlertDetailDialog', () => {
  it('renders evidence as key-values with a mini map at the evidence position', async () => {
    renderDialog(ALERT, [P.tenantFleetRead]);
    expect(screen.getByText('Distance outside m')).toBeInTheDocument();
    expect(screen.getByText('42.5')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Alert evidence location' })).toBeInTheDocument();
    await waitFor(() => {
      expect(lastMap().getSource('alert-evidence')).toBeDefined();
    });
  });

  it('requires a note to resolve and sends it', async () => {
    const user = userEvent.setup();
    mocks.act.mockResolvedValue({ ...ALERT, status: 'RESOLVED', resolution_note: 'Moved back' });
    const onChanged = renderDialog(ALERT, [P.tenantFleetRead, P.tenantAlertManage]);
    await user.click(screen.getByRole('button', { name: 'Resolve' }));
    const dialogSubmit = await screen.findAllByRole('button', { name: 'Resolve' });
    await user.click(dialogSubmit[dialogSubmit.length - 1] as HTMLElement);
    expect(await screen.findByText('A resolution note is required')).toBeInTheDocument();
    expect(mocks.act).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Resolution note/), 'Moved back');
    await user.click(dialogSubmit[dialogSubmit.length - 1] as HTMLElement);
    await waitFor(() => {
      expect(mocks.act).toHaveBeenCalledWith(
        ALERT.id,
        { action: 'RESOLVE', note: 'Moved back' },
        expect.any(String),
      );
    });
    expect(onChanged).toHaveBeenCalled();
  });

  it('hides acknowledge / resolve without tenant.fleet.alert_manage', () => {
    renderDialog(ALERT, [P.tenantFleetRead]);
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
  });

  it('explains SUPERSEDED alerts and offers no actions', () => {
    renderDialog({ ...ALERT, status: 'SUPERSEDED' }, [P.tenantFleetRead, P.tenantAlertManage]);
    expect(screen.getByText(/re-evaluated after late telemetry/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
  });
});
