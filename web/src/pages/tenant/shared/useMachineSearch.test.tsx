import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { machineService } from '../../../api/services/machineService';
import { SessionContext } from '../../../session/SessionContext';
import { makeMe, makeSession, TENANT_A } from '../../../test/fixtures';
import { useMachineSearch } from './useMachineSearch';

function hookWith(perms: string[]) {
  const me = makeMe();
  const session = makeSession(
    { ...me, tenants: me.tenants.map((t) => ({ ...t, permissions: perms })) },
    { kind: 'tenant', tenantId: TENANT_A },
  );
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
  );
  return renderHook(() => useMachineSearch(), { wrapper }).result.current;
}

describe('useMachineSearch', () => {
  it('searches the register with machine read, else only the caller’s own machines', async () => {
    const list = vi
      .spyOn(machineService, 'list')
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    const field = vi.spyOn(machineService, 'fieldMachines').mockResolvedValue([]);
    const signal = new AbortController().signal;

    await hookWith(['tenant.machine.read'])('EX', signal);
    expect(list).toHaveBeenCalledTimes(1);
    expect(field).not.toHaveBeenCalled();

    await hookWith(['tenant.machine_report.submit'])('EX', signal);
    expect(field).toHaveBeenCalledWith('EX', signal);
    expect(list).toHaveBeenCalledTimes(1); // a supervisor never calls the register (it answers 403)
  });
});
