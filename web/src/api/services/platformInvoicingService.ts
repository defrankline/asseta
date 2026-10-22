import { createContext, useContext } from 'react';
import type {
  AdHocInvoiceIn,
  AllocatePaymentIn,
  InvoiceDto,
  LifecycleChangeIn,
  PaymentDto,
  ProductDto,
  ProductIn,
  ProductPage,
  ProductUpdateIn,
  SmsWalletDto,
  SmsWalletEntryPage,
  VoidInvoiceIn,
} from '../types';
import { platformInvoiceService } from './platformInvoiceService';
import { platformPaymentService } from './platformPaymentService';
import { productService, type ProductListQuery } from './productService';
import { smsWalletService } from './smsWalletService';

/**
 * Platform commerce used by the DEC-022 screens (catalog, ad-hoc invoices, per-line payments and
 * fulfilment, SMS wallets), injectable through `PlatformInvoicingServiceContext` so tests can use
 * `src/test/fakePlatformInvoicingService.ts`. The default is the HTTP implementation.
 */
export interface PlatformInvoicingService {
  listProducts: (query: ProductListQuery, signal?: AbortSignal) => Promise<ProductPage>;
  getProduct: (id: string, signal?: AbortSignal) => Promise<ProductDto>;
  createProduct: (body: ProductIn, idempotencyKey: string) => Promise<ProductDto>;
  updateProduct: (id: string, body: ProductUpdateIn, idempotencyKey: string) => Promise<ProductDto>;
  deactivateProduct: (
    id: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ) => Promise<ProductDto>;
  reactivateProduct: (
    id: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ) => Promise<ProductDto>;
  /** Server-computed preview; nothing is saved (a fresh key per call). */
  previewInvoice: (body: AdHocInvoiceIn, idempotencyKey: string) => Promise<InvoiceDto>;
  raiseInvoice: (body: AdHocInvoiceIn, idempotencyKey: string) => Promise<InvoiceDto>;
  getInvoice: (id: string, signal?: AbortSignal) => Promise<InvoiceDto>;
  voidInvoice: (id: string, body: VoidInvoiceIn, idempotencyKey: string) => Promise<InvoiceDto>;
  /** The tenant's payments (one page of up to 200, the API maximum). */
  listTenantPayments: (tenantId: string, signal?: AbortSignal) => Promise<PaymentDto[]>;
  allocatePayment: (
    paymentId: string,
    body: AllocatePaymentIn,
    idempotencyKey: string,
  ) => Promise<PaymentDto>;
  /** `tenantId` in the platform console; null = the active tenant (tenant console). */
  getSmsWallet: (tenantId: string | null, signal?: AbortSignal) => Promise<SmsWalletDto>;
  listSmsWalletEntries: (
    tenantId: string | null,
    query: { page: number; page_size: number },
    signal?: AbortSignal,
  ) => Promise<SmsWalletEntryPage>;
}

export const httpPlatformInvoicingService: PlatformInvoicingService = {
  listProducts: (q, s) => productService.list(q, s),
  getProduct: (id, s) => productService.get(id, s),
  createProduct: (b, k) => productService.create(b, k),
  updateProduct: (id, b, k) => productService.update(id, b, k),
  deactivateProduct: (id, b, k) => productService.deactivate(id, b, k),
  reactivateProduct: (id, b, k) => productService.reactivate(id, b, k),
  previewInvoice: (b, k) => platformInvoiceService.preview(b, k),
  raiseInvoice: (b, k) => platformInvoiceService.raise(b, k),
  getInvoice: (id, s) => platformInvoiceService.get(id, s),
  voidInvoice: (id, b, k) => platformInvoiceService.void(id, b, k),
  listTenantPayments: async (tenantId, s) =>
    (await platformPaymentService.list({ page: 1, page_size: 200, tenant_id: tenantId }, s)).items,
  allocatePayment: (id, b, k) => platformPaymentService.allocate(id, b, k),
  getSmsWallet: (t, s) => smsWalletService.get(t, s),
  listSmsWalletEntries: (t, q, s) => smsWalletService.entries(t, q, s),
};

export const PlatformInvoicingServiceContext = createContext<PlatformInvoicingService>(
  httpPlatformInvoicingService,
);

export function usePlatformInvoicingService(): PlatformInvoicingService {
  return useContext(PlatformInvoicingServiceContext);
}
