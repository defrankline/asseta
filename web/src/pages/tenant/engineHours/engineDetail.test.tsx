import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import type { engineHoursService } from '../../../api/services/engineHoursService';
import type { CorrectionDto } from '../../../api/types';
import { recordPath, recordRoutePattern } from '../../../navigation/recordRoutes';
import { MACHINE_ID, ME_ID } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MeterCorrectionDetailPage } from './EngineRecordDetailPages';

const mocks = vi.hoisted(() => ({
  getCorrection: vi.fn<typeof engineHoursService.getCorrection>(),
}));
vi.mock('../../../api/services/engineHoursService', () => ({ engineHoursService: mocks }));

const OTHER = '44444444-4444-4444-8444-444444444444';

const correction = (over: Partial<CorrectionDto> = {}): CorrectionDto => ({
  id: 'cccccccc-0000-4000-8000-000000000009',
  machine_id: MACHINE_ID,
  machine_code: 'EX-01',
  machine_name: 'Excavator',
  job_id: 'dddddddd-0000-4000-8000-000000000001',
  job_number: 'J-100',
  old_reading: '1000.0',
  new_reading: '1001.0',
  reason: 'Typed the wrong digit',
  superseded_capture_id: 'aaaaaaaa-0000-4000-8000-000000000001',
  replacement_capture_id: 'aaaaaaaa-0000-4000-8000-000000000002',
  status: 'PROPOSED',
  proposed_by: ME_ID,
  proposed_by_name: 'Me',
  proposed_at: '2026-10-20T06:01:00Z',
  decided_by: null,
  decided_at: null,
  decision_note: null,
  policy_version: 'EH:P1',
  ...over,
});

function renderAt(id: string) {
  return renderWithProviders(
    <Routes>
      <Route
        path={recordRoutePattern('METER_CORRECTION')}
        element={<MeterCorrectionDetailPage />}
      />
    </Routes>,
    {
      tenantPermissions: ['tenant.meter.read', 'tenant.meter.approve'],
      route: recordPath('METER_CORRECTION', id),
    },
  );
}

describe('MeterCorrectionDetailPage', () => {
  it('loads by id with names, the machine ledger link and own-request Decide disabled', async () => {
    mocks.getCorrection.mockResolvedValue(correction());
    renderAt('cccccccc-0000-4000-8000-000000000009');
    expect(
      await screen.findByRole('heading', { name: 'Correction · EX-01 · Excavator' }),
    ).toBeInTheDocument();
    expect(mocks.getCorrection).toHaveBeenCalledWith(
      'cccccccc-0000-4000-8000-000000000009',
      expect.any(AbortSignal),
    );
    expect(screen.getByRole('link', { name: 'J-100' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Engine hours' })).toHaveAttribute(
      'href',
      `/tenant/engine-hours/machines/${MACHINE_ID}`,
    );
    expect(screen.getByRole('button', { name: 'Decide' })).toBeDisabled();
    expect(screen.getByText(/Someone else must decide your own request/)).toBeInTheDocument();
  });

  it('shows the decision in the history', async () => {
    mocks.getCorrection.mockResolvedValue(
      correction({
        proposed_by: OTHER,
        proposed_by_name: 'Asha Mwita',
        status: 'REJECTED',
        decided_by: OTHER,
        decided_by_name: 'Baraka Juma',
        decided_at: '2026-10-21T06:00:00Z',
        decision_note: 'Photo shows 1000.0',
      }),
    );
    renderAt('x');
    const history = await screen.findByRole('list', { name: 'History' });
    expect(history).toHaveTextContent('Asha Mwita');
    expect(history).toHaveTextContent('Baraka Juma');
    expect(history).toHaveTextContent('Photo shows 1000.0');
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });
});
