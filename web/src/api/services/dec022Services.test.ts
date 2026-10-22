import { beforeEach, describe, expect, it, vi } from 'vitest';
import { makeDelivery, makeNotification, makePreference } from '../../test/fakeNotificationService';
import {
  LEDGER,
  makeInvoice,
  makePlatformPayment,
  SMS_5K,
  WALLET,
} from '../../test/fakePlatformInvoicingService';
import type { ApiClient } from '../client';
import { createHttpNotificationService } from './notificationService';
import { platformInvoiceService } from './platformInvoiceService';
import { platformPaymentService } from './platformPaymentService';
import { productService } from './productService';
import { smsWalletService } from './smsWalletService';

const api = vi.hoisted(() => ({
  get: vi.fn<ApiClient['get']>(),
  post: vi.fn<ApiClient['post']>(),
  put: vi.fn<ApiClient['put']>(),
  patch: vi.fn<ApiClient['patch']>(),
  delete: vi.fn<ApiClient['delete']>(),
}));
vi.mock('../client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../client')>();
  return { ...actual, apiClient: api };
});

const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 20 });

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.put.mockReset();
});

describe('notification HTTP service', () => {
  it('uses /tenant/notifications with X-Tenant-ID in the tenant console', async () => {
    const svc = createHttpNotificationService('tenant');
    api.get.mockResolvedValue(page([makeNotification()]));
    await svc.list({
      page: 2,
      page_size: 15,
      unread_only: true,
      severity: 'CRITICAL',
      q: ' fuel ',
    });
    expect(api.get).toHaveBeenCalledWith('/tenant/notifications', {
      tenantScoped: true,
      params: { page: 2, page_size: 15, q: 'fuel', unread_only: true, severity: 'CRITICAL' },
    });
    expect(svc.testSend).toBeUndefined();
  });

  it('uses /platform/notifications without tenant scoping, incl. test-send', async () => {
    const svc = createHttpNotificationService('platform');
    api.get.mockResolvedValue({ count: 4 });
    expect(await svc.unreadCount()).toBe(4);
    expect(api.get).toHaveBeenCalledWith('/platform/notifications/unread-count', {
      tenantScoped: false,
    });
    api.post.mockResolvedValue({ updated: 2, unread: 1 });
    expect(await svc.markRead(['a', 'b'], 'k1')).toEqual({ updated: 2, unread: 1 });
    expect(api.post).toHaveBeenCalledWith(
      '/platform/notifications/read',
      { ids: ['a', 'b'] },
      { tenantScoped: false, idempotencyKey: 'k1' },
    );
    api.post.mockResolvedValue({ notification: makeNotification(), delivery: makeDelivery() });
    await svc.testSend?.({ title: 'T', body: 'B', msisdn: null }, 'k2');
    expect(api.post).toHaveBeenLastCalledWith(
      '/platform/notifications/test-send',
      { title: 'T', body: 'B', msisdn: null },
      { tenantScoped: false, idempotencyKey: 'k2' },
    );
  });

  it('reads and writes preferences (tenant defaults), profile and the delivery log', async () => {
    const svc = createHttpNotificationService('tenant');
    api.get.mockResolvedValue([makePreference()]);
    await svc.getPreferences(true);
    expect(api.get).toHaveBeenLastCalledWith('/tenant/notifications/preferences', {
      tenantScoped: true,
      params: { tenant_default: true },
    });
    api.put.mockResolvedValue([makePreference()]);
    const body = {
      changes: [{ type: 'ALERT_RAISED', in_app: true, sms: true }],
      tenant_default: true,
    };
    await svc.updatePreferences(body, 'k');
    expect(api.put).toHaveBeenLastCalledWith('/tenant/notifications/preferences', body, {
      tenantScoped: true,
      idempotencyKey: 'k',
    });
    api.put.mockResolvedValue({ user_id: 'u', msisdn: '+255712345678' });
    await svc.updateProfile({ msisdn: '+255 712 345 678' }, 'k3');
    expect(api.put).toHaveBeenLastCalledWith(
      '/tenant/notifications/profile',
      { msisdn: '+255 712 345 678' },
      { tenantScoped: true, idempotencyKey: 'k3' },
    );
    api.get.mockResolvedValue(page([makeDelivery()]));
    await svc.listDeliveries({ page: 1, page_size: 25, status: 'FAILED' });
    expect(api.get).toHaveBeenLastCalledWith('/tenant/notifications/deliveries', {
      tenantScoped: true,
      params: { page: 1, page_size: 25, status: 'FAILED' },
    });
  });

  it('rejects a contract mismatch', async () => {
    const svc = createHttpNotificationService('platform');
    api.get.mockResolvedValue(page([{ ...makeNotification(), severity: 'SUCCESS' }]));
    await expect(svc.list({ page: 1, page_size: 20 })).rejects.toMatchObject({
      code: 'contract_mismatch',
    });
  });
});

describe('platform commerce HTTP services', () => {
  it('lists products with server filters', async () => {
    api.get.mockResolvedValue(page([SMS_5K]));
    await productService.list({
      page: 1,
      page_size: 20,
      q: 'sms',
      product_type: 'SMS_BUNDLE',
      include_inactive: true,
    });
    expect(api.get).toHaveBeenCalledWith('/platform/products', {
      params: {
        page: 1,
        page_size: 20,
        q: 'sms',
        product_type: 'SMS_BUNDLE',
        include_inactive: 'true',
      },
    });
  });

  it('previews, raises and voids ad-hoc invoices with idempotency keys', async () => {
    api.post.mockResolvedValue(makeInvoice());
    const body = {
      tenant_id: 't',
      lines: [{ product_id: SMS_5K.id, quantity: '1', discount_percent: '0' }],
    };
    await platformInvoiceService.preview(body, 'p1');
    await platformInvoiceService.raise(body, 'r1');
    await platformInvoiceService.void('inv 1', { reason: 'Raised in error' }, 'v1');
    expect(api.post.mock.calls).toEqual([
      ['/platform/invoices/preview', body, { idempotencyKey: 'p1' }],
      ['/platform/invoices', body, { idempotencyKey: 'r1' }],
      ['/platform/invoices/inv%201/void', { reason: 'Raised in error' }, { idempotencyKey: 'v1' }],
    ]);
  });

  it('allocates a payment and filters payments by tenant', async () => {
    api.post.mockResolvedValue(makePlatformPayment());
    const body = { allocations: [{ line_id: 'l-sms', amount: '10.00' }] };
    await platformPaymentService.allocate('pay-1', body, 'a1');
    expect(api.post).toHaveBeenCalledWith('/platform/payments/pay-1/allocations', body, {
      idempotencyKey: 'a1',
    });
    api.get.mockResolvedValue(page([makePlatformPayment({ invoice_id: null })]));
    const res = await platformPaymentService.list({ page: 1, page_size: 200, tenant_id: 't' });
    expect(res.items[0]?.invoice_id).toBeNull();
    expect(api.get).toHaveBeenCalledWith('/platform/payments', {
      params: { page: 1, page_size: 200, tenant_id: 't' },
    });
  });

  it('reads SMS wallets in both consoles', async () => {
    api.get.mockResolvedValue(WALLET);
    await smsWalletService.get(null);
    expect(api.get).toHaveBeenLastCalledWith('/tenant/billing/sms-wallet', { tenantScoped: true });
    await smsWalletService.get('t 1');
    expect(api.get).toHaveBeenLastCalledWith('/platform/tenants/t%201/sms-wallet', {
      tenantScoped: false,
    });
    api.get.mockResolvedValue(page(LEDGER));
    await smsWalletService.entries('t', { page: 2, page_size: 25 });
    expect(api.get).toHaveBeenLastCalledWith('/platform/tenants/t/sms-wallet/entries', {
      tenantScoped: false,
      params: { page: 2, page_size: 25 },
    });
  });
});
