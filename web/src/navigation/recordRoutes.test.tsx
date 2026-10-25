import { screen } from '@testing-library/react';
import { Route, Routes, useLocation } from 'react-router';
import { describe, expect, it } from 'vitest';
import { notificationTargetPath } from '../notifications/center/display';
import { LegacyCashRedirect } from '../routes/LegacyCashRedirect';
import { renderWithProviders } from '../test/renderWithProviders';
import { isRecordKind, RECORD_LIST_ROUTES, recordPath, recordRoutePattern } from './recordRoutes';
import { IMPLEMENTED_PATHS } from './routes';

function Where() {
  const { pathname } = useLocation();
  return <p>at {pathname}</p>;
}

describe('exact-record routes (G5)', () => {
  it('builds the detail route of every kind from the kind → route table', () => {
    expect(recordPath('CASH_TRANSFER', 't 1')).toBe('/tenant/finance/cash/transfers/t%201');
    expect(recordPath('REMITTANCE_OVERDUE', 'o1')).toBe(
      '/tenant/finance/cash/remittance-overdue/o1',
    );
    expect(recordPath('HOURS_CREDIT', 'c1')).toBe('/tenant/hours/credit/c1');
    expect(recordRoutePattern('ENGINE_HOURS_CLASSIFICATION')).toBe(
      '/tenant/engine-hours/classifications/:id',
    );
    for (const list of Object.values(RECORD_LIST_ROUTES))
      expect(IMPLEMENTED_PATHS.has(list)).toBe(true);
    expect(isRecordKind('CASH_FLOAT')).toBe(true);
    expect(isRecordKind('toString')).toBe(false);
  });

  it('opens the exact record of a notification from data.kind + data.record_id', () => {
    const target = { entity: 'cash_transfer', id: 't1', path: '/tenant/cash/transfers' };
    expect(notificationTargetPath(target, { kind: 'CASH_TRANSFER', record_id: 't1' })).toBe(
      '/tenant/finance/cash/transfers/t1',
    );
    expect(notificationTargetPath(null, { kind: 'REMITTANCE_OVERDUE', record_id: 'o1' })).toBe(
      '/tenant/finance/cash/remittance-overdue/o1',
    );
    // Without data the record's entity and id still open it.
    expect(notificationTargetPath({ entity: 'cash_handover', id: 'h1', path: null })).toBe(
      '/tenant/finance/cash/remittances/h1',
    );
    expect(notificationTargetPath({ entity: 'baseline', id: 'b1', path: null })).toBe(
      '/tenant/meter-baselines/b1',
    );
    // Unknown kinds fall back to the link.
    expect(
      notificationTargetPath(
        { entity: 'job', id: 'j1', path: '/tenant/jobs/j1' },
        { kind: 'SOMETHING', record_id: 'x' },
      ),
    ).toBe('/tenant/jobs/j1');
  });

  it('sends older /tenant/cash/<list>/<id> links to the console route', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/tenant/cash/*" element={<LegacyCashRedirect />} />
        <Route path="*" element={<Where />} />
      </Routes>,
      { tenantPermissions: [], route: '/tenant/cash/handovers/h1' },
    );
    expect(await screen.findByText('at /tenant/finance/cash/remittances/h1')).toBeInTheDocument();
  });
});
