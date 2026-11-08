import { screen, waitFor } from '@testing-library/react';
import { Formik } from 'formik';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { OverviewFleetSectionDto } from '../api/types';
import { tileOfDisabledCapability } from '../pages/tenant/accountability/tileCapabilities';
import { FleetSection } from '../pages/tenant/dashboard/DashboardSections';
import { RemittanceDepositFields } from '../pages/tenant/finance/cash/remittanceDeposit';
import { GeofencesPage } from '../pages/tenant/geofences/GeofencesPage';
import { renderWithProviders } from '../test/renderWithProviders';
import {
  CAPABILITY,
  CAPABILITY_FEATURE,
  pathCapability,
  type CapabilityCode,
} from './capabilities';
import { PERMISSIONS as P } from './permissionCodes';
import { RequireCapability } from './RequireCapability';

const geo = vi.hoisted(() => ({ list: vi.fn(), listJobSites: vi.fn() }));
vi.mock('../api/services/geofenceService', () => ({ geofenceService: geo }));
vi.mock('../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));
vi.mock('../pages/tenant/geofences/GeofencesMap', () => ({ GeofencesMap: () => <p>map</p> }));
vi.mock('../pages/tenant/finance/depositAccounts/depositAccountPickers', () => ({
  FormikDepositAccountIdPicker: () => <p>account picker</p>,
}));

beforeEach(() => {
  geo.list.mockResolvedValue([]);
  geo.listJobSites.mockResolvedValue([]);
});

const SWITCHES: readonly [CapabilityCode, string][] = [
  [CAPABILITY.insights, '/tenant/insights'],
  [CAPABILITY.investigations, '/tenant/cases/c1'],
  [CAPABILITY.tracking, '/tenant/trackers/t1'],
  [CAPABILITY.tracking, '/tenant/alerts'],
  [CAPABILITY.depositAccounts, '/tenant/finance/deposit-accounts/a1'],
  [CAPABILITY.managedService, '/tenant/managed-service'],
];

describe('optional module switches', () => {
  it.each(SWITCHES)('%s owns %s and shows the not-enabled state', (code, path) => {
    expect(pathCapability(path)).toBe(code);
    renderWithProviders(
      <RequireCapability capability={code} feature={CAPABILITY_FEATURE[code]}>
        <p>the page</p>
      </RequireCapability>,
      { tenantPermissions: [P.tenantFleetRead], disabledCapabilities: [code] },
    );
    expect(screen.queryByText('the page')).not.toBeInTheDocument();
    expect(screen.getByText(/is not enabled for your company/)).toBeInTheDocument();
  });

  it('keeps every page while the switches are on (the default)', () => {
    renderWithProviders(
      <RequireCapability capability={CAPABILITY.tracking} feature="Tracking">
        <p>the page</p>
      </RequireCapability>,
      { tenantPermissions: [P.tenantFleetRead], disabledCapabilities: [] },
    );
    expect(screen.getByText('the page')).toBeInTheDocument();
  });

  it('job sites stay when tracking is off, and geofences are never requested', async () => {
    renderWithProviders(<GeofencesPage />, {
      tenantPermissions: [P.tenantGeofenceRead, P.tenantGeofenceWrite],
      disabledCapabilities: [CAPABILITY.tracking],
    });
    expect(await screen.findByRole('heading', { name: 'Job sites', level: 1 })).toBeInTheDocument();
    await waitFor(() => {
      expect(geo.listJobSites).toHaveBeenCalled();
    });
    expect(geo.list).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'New geofence' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New job site' })).toBeInTheDocument();
  });

  it('shows geofences by default', async () => {
    renderWithProviders(<GeofencesPage />, {
      tenantPermissions: [P.tenantGeofenceRead, P.tenantGeofenceWrite],
      disabledCapabilities: [],
    });
    expect(await screen.findByRole('button', { name: 'New geofence' })).toBeInTheDocument();
    await waitFor(() => {
      expect(geo.list).toHaveBeenCalled();
    });
  });

  it('hides the connectivity and alert figures of the fleet dashboard when tracking is off', () => {
    const fleet = {
      machines: 2,
      connectivity: { live: 1, recent: 0, stale: 0, offline: 1, never: 0, no_tracker: 0 },
      reported_work_state: {},
      engine_on_verified: 1,
      open_alerts: { info: 0, warning: 1, critical: 0 },
      latest_source_at: null,
    } as unknown as OverviewFleetSectionDto;
    const props = { data: fleet, can: () => true, nowMs: 0, timeZone: 'UTC' };
    const { unmount } = renderWithProviders(<FleetSection {...props} />, {
      tenantPermissions: [P.tenantFleetRead],
      disabledCapabilities: [],
    });
    expect(screen.getByText('Open alerts')).toBeInTheDocument();
    unmount();
    renderWithProviders(<FleetSection {...props} />, {
      tenantPermissions: [P.tenantFleetRead],
      disabledCapabilities: [CAPABILITY.tracking],
    });
    expect(screen.getByText('Machines')).toBeInTheDocument();
    expect(screen.queryByText('Open alerts')).not.toBeInTheDocument();
    expect(screen.queryByText('Engine on (verified)')).not.toBeInTheDocument();
  });

  it('drops the investigations tile with its capability', () => {
    expect(tileOfDisabledCapability('investigations', new Set([CAPABILITY.investigations]))).toBe(
      true,
    );
    expect(tileOfDisabledCapability('investigations', new Set())).toBe(false);
  });

  it('hides the company account picker when deposit accounts are off', () => {
    const fields = (
      <Formik
        initialValues={{ method: 'CASH_TO_OFFICE', currency: 'TZS', evidence: [] }}
        onSubmit={() => undefined}
      >
        <RemittanceDepositFields
          requirements={{ reference: false, evidence: false, account: false }}
          onAccountChange={() => undefined}
          account={null}
        />
      </Formik>
    );
    const { unmount } = renderWithProviders(fields, {
      tenantPermissions: [P.tenantCollectionRecord],
      disabledCapabilities: [],
    });
    expect(screen.getByText('account picker')).toBeInTheDocument();
    unmount();
    renderWithProviders(fields, {
      tenantPermissions: [P.tenantCollectionRecord],
      disabledCapabilities: [CAPABILITY.depositAccounts],
    });
    expect(screen.queryByText('account picker')).not.toBeInTheDocument();
  });
});
