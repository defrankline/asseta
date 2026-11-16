import { describe, expect, it } from 'vitest';
import { CAPABILITY } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { notificationTargetPath } from '../../../notifications/center/display';
import { buildTiles } from '../accountability/accountabilityModel';

describe('dashboard tiles and notifications', () => {
  const SUMMARY = {
    as_of: '2026-10-26T12:00:00Z',
    policy_version: 'v1',
    hidden_tiles: [],
    unavailable_tiles: [],
    disabled_capabilities: [],
    unbilled_work: {
      count: 2,
      after_days: 7,
      amounts: [{ currency: 'TZS', count: 1, amount: '2000000' }],
      oldest_days: 16,
      items: [
        {
          job_id: 'j1',
          job_number: 'J-001',
          machine_id: 'm1',
          machine_code: 'EX-01',
          machine_name: 'Excavator',
          customer_id: 'c1',
          customer_name: 'Road Builders',
          completed_at: '',
          days_unbilled: 16,
          currency: 'TZS',
          total: '2000000',
        },
      ],
    },
    idle_machines: {
      count: 1,
      after_days: 14,
      longest_idle_days: 25,
      items: [
        {
          machine_id: 'm3',
          machine_code: 'GR-03',
          machine_name: 'Grader',
          idle_since: '',
          idle_days: 25,
          planned_job_id: 'j8',
          planned_job_number: 'J-008',
        },
      ],
    },
  } as unknown as AccountabilitySummaryDto;

  it('builds the unbilled work and idle machines tiles linking to their lists', () => {
    const tiles = buildTiles(SUMMARY, () => true);
    const unbilled = tiles.find((t) => t.key === 'unbilled_work');
    expect(unbilled?.value).toBe(2);
    expect(unbilled?.to).toBe('/tenant/unbilled-work');
    expect(unbilled?.description).toBe('Oldest 16 days');
    const idle = tiles.find((t) => t.key === 'idle_machines');
    expect(idle?.to).toBe('/tenant/idle-machines');
    expect(idle?.rows?.find((r) => r.key === 'planned')?.value).toBe(1);
  });

  it('lists the tile items by name, linking to the record', () => {
    const tiles = buildTiles(SUMMARY, () => true);
    const job = tiles.find((t) => t.key === 'unbilled_work')?.rows?.find((r) => r.key === 'job-j1');
    expect(job?.label).toBe('J-001 · Road Builders · EX-01 Excavator');
    expect(job?.valueText).toBe('TZS 2,000,000.00, 16 days');
    expect(job?.to).toBe('/tenant/jobs/j1');
    const machine = tiles
      .find((t) => t.key === 'idle_machines')
      ?.rows?.find((r) => r.key === 'machine-m3');
    expect(machine?.label).toBe('GR-03 Grader (planned J-008)');
    expect(machine?.valueText).toBe('25 days');
    expect(machine?.to).toBe('/tenant/machines/m3');
    const noAccess = buildTiles(SUMMARY, () => false);
    expect(
      noAccess.find((t) => t.key === 'unbilled_work')?.rows?.find((r) => r.key === 'job-j1')?.to,
    ).toBeUndefined();
  });

  it('drops the tiles while their capability is off', () => {
    const off = {
      ...SUMMARY,
      disabled_capabilities: [CAPABILITY.unbilledWork, CAPABILITY.idleMachines],
    };
    const keys = buildTiles(off, () => true).map((t) => t.key);
    expect(keys).not.toContain('unbilled_work');
    expect(keys).not.toContain('idle_machines');
  });

  it('opens the job from an UNBILLED_WORK notification', () => {
    expect(notificationTargetPath(null, { kind: 'JOB', record_id: 'j1' })).toBe('/tenant/jobs/j1');
  });
});
