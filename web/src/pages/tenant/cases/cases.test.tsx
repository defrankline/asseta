import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { caseService, riskSignalService } from '../../../api/services/caseService';
import type { peopleService } from '../../../api/services/peopleService';
import { CASE_ID, makeCase, makeDetail, makeRiskSignal, PERSON } from '../../../test/caseFixtures';
import { page } from '../../../test/financeFixtures';
import { notificationTargetPath } from '../../../notifications/center/display';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { resetPersonDirectory } from '../shared/personDirectory';
import { CasesPage } from './CasesPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn<typeof caseService.list>(),
  get: vi.fn<typeof caseService.get>(),
  signals: vi.fn<typeof riskSignalService.list>(),
  people: vi.fn<typeof peopleService.list>(),
  search: vi.fn<typeof peopleService.search>(),
}));
vi.mock('../../../api/services/caseService', () => ({
  caseService: { list: mocks.list, get: mocks.get },
  riskSignalService: { list: mocks.signals },
}));
vi.mock('../../../api/services/peopleService', () => ({
  PEOPLE_BATCH: 100,
  peopleService: { list: mocks.people, search: mocks.search },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));
vi.mock('../../../api/services/staffService', () => ({
  staffService: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 }),
  },
}));

const READ = [P.tenantCaseRead, P.tenantDirectoryRead];

beforeEach(() => {
  resetPersonDirectory();
  mocks.list.mockResolvedValue(
    page([makeCase({ assignee_user_id: PERSON.user_id, signal_count: 2 })]),
  );
  mocks.get.mockResolvedValue(makeDetail());
  mocks.signals.mockResolvedValue(page([makeRiskSignal()]));
  mocks.people.mockResolvedValue([PERSON]);
  mocks.search.mockResolvedValue([PERSON]);
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderPage(permissions: string[], route = '/tenant/cases') {
  renderWithProviders(
    <Routes>
      <Route path="/tenant/cases" element={<CasesPage />} />
      <Route path="/tenant/cases/:caseId" element={<p>Case page</p>} />
    </Routes>,
    { tenantPermissions: permissions, route },
  );
}

describe('CasesPage', () => {
  it('lists cases with neutral chips, assignee name and the Open status by default', async () => {
    renderPage(READ);
    expect(await screen.findByText('CASE-2026-00001')).toBeInTheDocument();
    const row = screen.getByText('CASE-2026-00001').closest('tr');
    expect(row).not.toBeNull();
    const cells = within(row as HTMLElement);
    expect(cells.getByText('Needs review')).toBeInTheDocument();
    expect(cells.getByText('Warning')).toBeInTheDocument();
    expect(await cells.findByText('Rita Reviewer')).toBeInTheDocument();
    expect(cells.getByText('2')).toBeInTheDocument();
    expect(mocks.list.mock.lastCall?.[0].filters).toMatchObject({ status: 'OPEN' });
    expect(screen.getByText(/They are not a conclusion about any person/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fraud/i);
  });

  it('filters by a server-searched assignee, severity and free text', async () => {
    const user = userEvent.setup();
    renderPage(READ);
    await screen.findByText('CASE-2026-00001');
    const assignee = screen.getByRole('combobox', { name: 'Assignee' });
    await user.click(assignee);
    await user.type(assignee, 'rit');
    await waitFor(() => {
      expect(mocks.search).toHaveBeenCalledWith('rit', expect.any(AbortSignal));
    });
    await user.click(await screen.findByRole('option', { name: 'Rita Reviewer' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters?.assignee_user_id).toBe(PERSON.user_id);
    });
    await user.click(screen.getByRole('combobox', { name: 'Severity' }));
    await user.click(await screen.findByRole('option', { name: 'Critical' }));
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].filters?.severity).toBe('CRITICAL');
    });
    await user.type(screen.getByPlaceholderText('Search case number or title'), 'CASE-2026');
    await waitFor(() => {
      expect(mocks.list.mock.lastCall?.[0].q).toBe('CASE-2026');
    });
  });

  it('opens a case from its row', async () => {
    const user = userEvent.setup();
    renderPage(READ);
    await user.click(await screen.findByText('CASE-2026-00001'));
    expect(await screen.findByText('Case page')).toBeInTheDocument();
  });

  it('hides the Signals tab without tenant.signal.read', async () => {
    renderPage(READ, '/tenant/cases?tab=signals');
    expect(await screen.findByText('CASE-2026-00001')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Signals' })).not.toBeInTheDocument();
    expect(mocks.signals).not.toHaveBeenCalled();
  });

  it('lists signals with an evidence summary and opens the case of a linked signal', async () => {
    const user = userEvent.setup();
    renderPage([...READ, P.tenantSignalRead]);
    await user.click(await screen.findByRole('tab', { name: 'Signals' }));
    expect(await screen.findByText('Engine activity without an active job')).toBeInTheDocument();
    expect(
      screen.getByText(/Verified engine activity \(ignition on\) was recorded/),
    ).toBeInTheDocument();
    expect(screen.getByText('On a case')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Signal' }));
    await user.click(
      await screen.findByRole('option', { name: 'Same receipt image on more than one expense' }),
    );
    await waitFor(() => {
      expect(mocks.signals.mock.lastCall?.[0].filters?.rule_code).toBe('DUPLICATE_RECEIPT');
    });
    await user.click(screen.getByText('Engine activity without an active job'));
    expect(await screen.findByText('Case page')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({
        filters: { subject_type: 'MACHINE', subject_id: makeRiskSignal().subject_id },
      }),
    );
    expect(mocks.get).toHaveBeenCalledWith(CASE_ID);
  });
});

describe('case notifications', () => {
  it('ANOMALY_DETECTED notifications open the case they link to', () => {
    expect(
      notificationTargetPath({ entity: 'case', id: CASE_ID, path: `/tenant/cases/${CASE_ID}` }),
    ).toBe(`/tenant/cases/${CASE_ID}`);
    // Without a server path the case entity still resolves to its details page.
    expect(notificationTargetPath({ entity: 'case', id: CASE_ID, path: null })).toBe(
      `/tenant/cases/${CASE_ID}`,
    );
    expect(notificationTargetPath({ entity: 'case', id: null, path: null })).toBe('/tenant/cases');
  });
});
