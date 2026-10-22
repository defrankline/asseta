import { screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS as P } from '../../../access/permissionCodes';
import type { peopleService } from '../../../api/services/peopleService';
import { makeMe } from '../../../test/fixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { PersonName } from './PersonName';
import { lookupPersonName, resetPersonDirectory } from './personDirectory';

const ACCOUNTANT = '4294e3e7-0000-4000-8000-000000000001';
const SUPERVISOR = '4294e3e7-0000-4000-8000-000000000002';
const STRANGER = '4294e3e7-0000-4000-8000-000000000003';

const mocks = vi.hoisted(() => ({ list: vi.fn<typeof peopleService.list>() }));
vi.mock('../../../api/services/peopleService', () => ({
  PEOPLE_BATCH: 2,
  peopleService: { list: mocks.list },
}));

beforeEach(() => {
  resetPersonDirectory();
  mocks.list.mockImplementation((ids) =>
    Promise.resolve(
      [
        { user_id: ACCOUNTANT, display_name: 'Demo Accountant' },
        { user_id: SUPERVISOR, display_name: 'Demo Supervisor' },
      ].filter((p) => ids.includes(p.user_id)),
    ),
  );
});
afterEach(() => {
  vi.clearAllMocks();
});

describe('PersonName', () => {
  it('shows colleagues by name with one batched request, "You" for me and the id for non-members', async () => {
    const me = makeMe().user_id;
    renderWithProviders(
      <>
        <PersonName userId={ACCOUNTANT} />|<PersonName userId={SUPERVISOR} />|
        <PersonName userId={STRANGER} />|<PersonName userId={me} />|
        <PersonName userId={null} empty="policy (auto)" />|<PersonName userId={ACCOUNTANT} />
      </>,
      { tenantPermissions: [P.tenantDirectoryRead] },
    );
    expect(await screen.findAllByText(/Demo Accountant/)).not.toHaveLength(0);
    const text = document.body.textContent;
    expect(text).toContain('Demo Supervisor');
    expect(text).toContain('4294e3e7…');
    expect(text).toContain('You');
    expect(text).toContain('policy (auto)');
    // 3 distinct ids (me is never looked up), PEOPLE_BATCH = 2 -> two requests in one tick.
    expect(mocks.list).toHaveBeenCalledTimes(2);
    expect(mocks.list.mock.calls.flatMap(([ids]) => ids).sort()).toEqual(
      [ACCOUNTANT, SUPERVISOR, STRANGER].sort(),
    );
  });

  it('keeps the short id without the directory permission and makes no request', () => {
    renderWithProviders(<PersonName userId={ACCOUNTANT} />, { tenantPermissions: [] });
    expect(screen.getByText('4294e3e7…')).toBeInTheDocument();
    expect(mocks.list).not.toHaveBeenCalled();
  });
});

describe('lookupPersonName', () => {
  it('caches per tenant and resolves failures to null', async () => {
    await expect(lookupPersonName('t1', ACCOUNTANT)).resolves.toBe('Demo Accountant');
    await expect(lookupPersonName('t1', ACCOUNTANT)).resolves.toBe('Demo Accountant');
    expect(mocks.list).toHaveBeenCalledTimes(1);
    mocks.list.mockRejectedValueOnce(new Error('offline'));
    await expect(lookupPersonName('t2', ACCOUNTANT)).resolves.toBeNull();
  });
});
