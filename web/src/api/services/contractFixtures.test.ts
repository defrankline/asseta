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
    parse(machineReportContextSchema, 'machine-reports/context.json');
    parse(array(availableHoursSchema).required(), 'machine-reports/available-hours.json');
    parse(meterCaptureSchema, 'machine-reports/meter-capture-opening.json');
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
