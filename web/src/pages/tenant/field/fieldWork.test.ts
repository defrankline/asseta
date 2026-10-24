import { describe, expect, it } from 'vitest';
import type { ActivityDto } from '../../../api/types';
import { canvasPoint } from '../../../components/meter/signature';
import { isGranted } from '../../../session/permissions';
import { emptyCollectionValues, toFieldCollectionPayload } from './fieldCash';
import { activeStepIndex, FIELD_STEPS, isFieldUser, nextFieldStep, workTotals } from './fieldWork';

const activity = (overrides: Partial<ActivityDto>): ActivityDto => ({
  id: crypto.randomUUID(),
  client_id: crypto.randomUUID(),
  activity_type: 'WORK',
  started_at: '2026-10-21T08:00:00Z',
  ended_at: '2026-10-21T10:00:00Z',
  billable: true,
  note: null,
  ...overrides,
});

describe('nextFieldStep', () => {
  const base = { hasOpening: false, hasClosing: false, hasAcknowledgement: false };

  it('follows the server rules from opening reading to completion', () => {
    expect(nextFieldStep({ ...base, status: 'APPROVED' })).toBe('OPENING');
    expect(nextFieldStep({ ...base, status: 'APPROVED', hasOpening: true })).toBe('START');
    expect(nextFieldStep({ ...base, status: 'IN_PROGRESS', hasOpening: true })).toBe('CLOSING');
    expect(
      nextFieldStep({ ...base, status: 'IN_PROGRESS', hasOpening: true, hasClosing: true }),
    ).toBe('ACK');
    expect(
      nextFieldStep({
        status: 'IN_PROGRESS',
        hasOpening: true,
        hasClosing: true,
        hasAcknowledgement: true,
      }),
    ).toBe('COMPLETE');
  });

  it('asks for the closing reading even when the acknowledgement came first', () => {
    expect(nextFieldStep({ ...base, status: 'IN_PROGRESS', hasAcknowledgement: true })).toBe(
      'CLOSING',
    );
  });

  it('treats closed and unapproved jobs as done / waiting', () => {
    expect(nextFieldStep({ ...base, status: 'COMPLETED' })).toBe('DONE');
    expect(nextFieldStep({ ...base, status: 'CANCELLED' })).toBe('DONE');
    expect(nextFieldStep({ ...base, status: 'DRAFT' })).toBe('WAITING');
    expect(nextFieldStep({ ...base, status: 'PENDING_APPROVAL' })).toBe('WAITING');
  });

  it('maps steps onto the stepper', () => {
    expect(activeStepIndex('OPENING')).toBe(0);
    expect(activeStepIndex('ACK')).toBe(3);
    expect(activeStepIndex('DONE')).toBe(FIELD_STEPS.length);
    expect(activeStepIndex('WAITING')).toBe(-1);
  });
});

describe('workTotals', () => {
  it('sums closed entries per type and counts open ones without estimating them', () => {
    const t = workTotals([
      activity({}),
      activity({ started_at: '2026-10-21T11:00:00Z', ended_at: '2026-10-21T11:30:00Z' }),
      activity({
        activity_type: 'DOWNTIME',
        started_at: '2026-10-21T10:00:00Z',
        ended_at: '2026-10-21T11:00:00Z',
      }),
      activity({ activity_type: 'STANDBY', ended_at: null }),
    ]);
    expect(t.seconds.WORK).toBe(2.5 * 3600);
    expect(t.seconds.DOWNTIME).toBe(3600);
    expect(t.seconds.STANDBY).toBe(0);
    expect(t.open).toBe(1);
  });
});

describe('isFieldUser', () => {
  const has = (codes: string[]) => (p: string | readonly string[], m?: 'all' | 'any') =>
    isGranted(new Set(codes), p, m);

  it('is a job logger without office oversight', () => {
    expect(isFieldUser(has(['tenant.job.log', 'tenant.meter.capture']))).toBe(true);
    expect(isFieldUser(has(['tenant.job.log', 'tenant.job.approve']))).toBe(false);
    expect(isFieldUser(has(['tenant.job.log', 'tenant.finance.read']))).toBe(false);
    expect(isFieldUser(has(['tenant.finance.read']))).toBe(false);
  });
});

describe('toFieldCollectionPayload', () => {
  it('records into the caller’s own custody without allocations; the job is not sent', () => {
    const v = {
      ...emptyCollectionValues('2026-10-21T12:00:00Z', 'job-1'),
      customer_id: 'cust-1',
      amount: ' 250000 ',
      reference: ' RB-12 ',
    };
    expect(toFieldCollectionPayload(v, 'client-1')).toEqual({
      customer_id: 'cust-1',
      amount: '250000',
      currency: null,
      reference: 'RB-12',
      received_at: '2026-10-21T12:00:00Z',
      staff_member_id: null,
      note: null,
      client_id: 'client-1',
      allocations: [],
    });
  });
});

describe('canvasPoint', () => {
  it('scales screen coordinates to canvas pixels', () => {
    expect(canvasPoint(160, 70, { left: 10, top: 20, width: 300, height: 100 })).toEqual({
      x: 300,
      y: 100,
    });
    expect(canvasPoint(5, 5, { left: 0, top: 0, width: 0, height: 0 })).toEqual({ x: 5, y: 5 });
  });
});
