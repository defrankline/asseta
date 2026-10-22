import { apiClient, toListParams } from '../client';
import type {
  LifecycleChangeIn,
  ProductDto,
  ProductIn,
  ProductPage,
  ProductType,
  ProductUpdateIn,
} from '../types';
import { parseResponse } from '../validation';
import { productPageSchema, productSchema } from './commerceSchemas';

const BASE = '/platform/products';
const seg = (v: string) => encodeURIComponent(v);

export interface ProductListQuery {
  page: number;
  page_size: number;
  q?: string;
  sort?: string;
  product_type?: ProductType;
  include_inactive?: boolean;
}

async function send(url: string, method: 'post' | 'put', body: unknown, key: string) {
  const data = await apiClient[method]<unknown>(url, body, { idempotencyKey: key });
  return parseResponse(productSchema, data, 'product');
}

/** Platform product catalog (DEC-022, ADR-006): never deleted; deactivate / reactivate. */
export const productService = {
  /** GET /platform/products (listPlatformProducts). */
  async list(query: ProductListQuery, signal?: AbortSignal): Promise<ProductPage> {
    const { product_type, include_inactive, ...rest } = query;
    const data = await apiClient.get<unknown>(BASE, {
      params: toListParams({
        ...rest,
        filters: {
          product_type,
          include_inactive: include_inactive === true ? 'true' : undefined,
        },
      }),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(productPageSchema, data, 'product page');
  },
  /** GET /platform/products/{id} (getPlatformProduct). */
  async get(productId: string, signal?: AbortSignal): Promise<ProductDto> {
    const data = await apiClient.get<unknown>(
      `${BASE}/${seg(productId)}`,
      signal ? { signal } : undefined,
    );
    return parseResponse(productSchema, data, 'product');
  },
  /** POST /platform/products (createPlatformProduct). */
  create(body: ProductIn, idempotencyKey: string): Promise<ProductDto> {
    return send(BASE, 'post', body, idempotencyKey);
  },
  /** PUT /platform/products/{id} (updatePlatformProduct) with the `version` read. */
  update(productId: string, body: ProductUpdateIn, idempotencyKey: string): Promise<ProductDto> {
    return send(`${BASE}/${seg(productId)}`, 'put', body, idempotencyKey);
  },
  deactivate(productId: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return send(`${BASE}/${seg(productId)}/deactivate`, 'post', body, idempotencyKey);
  },
  reactivate(productId: string, body: LifecycleChangeIn, idempotencyKey: string) {
    return send(`${BASE}/${seg(productId)}/reactivate`, 'post', body, idempotencyKey);
  },
};
