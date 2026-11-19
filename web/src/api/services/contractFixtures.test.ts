import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { array, type Schema } from 'yup';
import { describe, expect, it } from 'vitest';
import { parseResponse } from '../validation';
import { creditInvoiceSchema, customerHoursSchema } from './creditInvoiceService';
import { hoursPurchaseSchema } from './hoursSchemas';
import {
  availableHoursSchema,
  machineReportContextSchema,
  machineReportSchema,
  machineReportStatusSchema,
} from './machineReportSchemas';
import { meterCaptureSchema } from './meterSchemas';
import { tenantPageSchema } from './tenantRequest';
import { formatVisitGap, whereLine } from '../../pages/tenant/machineReports/visitDisplay';

/**
 * Real server responses (contracts/fixtures, written by backend tests/api/test_contract_fixtures.py) through the
 * same runtime validation the services use: a schema that would reject what the server really sends fails here.
 */
const FIXTURES = resolve(__dirname, '../../../../contracts/fixtures');
const read = (path: string): unknown => JSON.parse(readFileSync(resolve(FIXTURES, path), 'utf8'));
const parse = <T>(schema: Schema<T>, path: string): T => parseResponse(schema, read(path), path);

describe('contract fixtures', () => {
  it('machine reports: opening, submitted, rejected, approved and the lists', () => {
    const opening = parse(machineReportSchema, 'machine-reports/report-opening-submitted.json');
    expect(opening.opening).toBe(true);
    expect(opening.start_source).toBe('OPENING');
    expect(opening.findings?.[0]?.type).toBe('GPS_INACCURATE');
    for (const name of ['report-submitted', 'report-rejected', 'report-approved']) {
      parse(machineReportSchema, `machine-reports/${name}.json`);
    }
    // Time since the previous visit and where both readings were taken.
    const approved = parse(machineReportSchema, 'machine-reports/report-approved.json');
    expect(formatVisitGap(approved.since_previous_visit_seconds)).toBe('1 h');
    expect(
      whereLine({
        place: approved.previous_visit_place,
        site: approved.previous_visit_site_name,
        lat: approved.previous_visit_lat,
        lng: approved.previous_visit_lng,
        accuracy: approved.previous_visit_accuracy_m,
      }),
    ).toBe('Where: Mbezi Beach, Kinondoni, Dar es Salaam · -6.8000, 39.2800 (±8 m)');
    const rejected = parse(machineReportSchema, 'machine-reports/report-rejected.json');
    expect(formatVisitGap(rejected.since_previous_visit_seconds)).toBe('First visit');
    expect(rejected.visit_place).toBe('Mbezi Beach, Kinondoni, Dar es Salaam');
    const page = tenantPageSchema(machineReportSchema);
    for (const name of ['list-pending', 'list-all', 'list-mine']) {
      expect(parse(page, `machine-reports/${name}.json`).items.length).toBeGreaterThan(0);
    }
  });

  it('report status, context, available hours and the reading', () => {
    const statuses = parse(
      array(machineReportStatusSchema).required(),
      'machine-reports/status.json',
    );
    expect(statuses.some((s) => s.opening_required)).toBe(true);
    expect(
      parse(machineReportContextSchema, 'machine-reports/context-opening-required.json')
        .opening_required,
    ).toBe(true);
    const context = parse(machineReportContextSchema, 'machine-reports/context.json');
    expect(context.last_visit_at).toBe('2026-11-01T18:00:00Z');
    expect(context.last_visit_lat).toBe(-6.8);
    expect(statuses.every((s) => s.last_visit_at !== undefined)).toBe(true);
    parse(array(availableHoursSchema).required(), 'machine-reports/available-hours.json');
    expect(
      parse(meterCaptureSchema, 'machine-reports/meter-capture-opening.json').place_name,
    ).toBeNull();
  });

  it('credit sales, credit invoices and customer hours', () => {
    const orders = tenantPageSchema(hoursPurchaseSchema);
    const [sale] = parse(orders, 'credit-sales/hours-purchases-credit-to-activate.json').items;
    expect(sale?.credit_status).toBe('AWAITING_ACTIVATION');
    expect(sale?.payments?.map((p) => p.method)).toEqual(['CASH']);
    parse(orders, 'credit-sales/hours-purchases-awaiting-activation.json');
    parse(tenantPageSchema(creditInvoiceSchema), 'credit-sales/credit-invoices.json');
    expect(parse(creditInvoiceSchema, 'credit-sales/credit-invoice.json').status).toBe('PART_PAID');
    parse(array(customerHoursSchema).required(), 'credit-sales/customer-hours.json');
  });
});
