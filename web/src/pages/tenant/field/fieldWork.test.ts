import { describe, expect, it } from 'vitest';
import { canvasPoint } from '../../../components/meter/signature';
import { isGranted } from '../../../session/permissions';
import { emptyCollectionValues, toFieldCollectionPayload } from './fieldCash';
import { isFieldUser } from './fieldWork';

describe('isFieldUser', () => {
  const has = (codes: string[]) => (p: string | readonly string[], m?: 'all' | 'any') =>
    isGranted(new Set(codes), p, m);

  it('submits machine reports without office oversight', () => {
    const submit = 'tenant.machine_report.submit';
    expect(isFieldUser(has([submit, 'tenant.meter.capture']))).toBe(true);
    expect(isFieldUser(has([submit, 'tenant.machine_report.approve']))).toBe(false);
    expect(isFieldUser(has([submit, 'tenant.finance.read']))).toBe(false);
    expect(isFieldUser(has(['tenant.finance.read']))).toBe(false);
  });
});

describe('toFieldCollectionPayload', () => {
  it('records into the caller’s own custody', () => {
    const v = {
      ...emptyCollectionValues('2026-10-21T12:00:00Z'),
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
      purchase_id: null,
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
