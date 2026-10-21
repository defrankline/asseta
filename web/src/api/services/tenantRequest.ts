import { apiClient, toListParams, type QueryParams } from '../client';
import type { Page } from '../types';
import { parseResponse } from '../validation';
import { array, object, type Schema } from 'yup';
import { int } from './schemaKit';

/** Tenant-scoped helpers: every call carries `X-Tenant-ID` for the active tenant. */

export interface TenantListQuery {
  page: number;
  page_size: number;
  sort?: string | undefined;
  q?: string | undefined;
  filters?: Readonly<Record<string, string | undefined>> | undefined;
}

function cleanParams(params: QueryParams | undefined): QueryParams | undefined {
  if (params === undefined) return undefined;
  const out: QueryParams = {};
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') out[k] = v;
  return out;
}

export async function tenantGet<T>(
  url: string,
  schema: Schema<T>,
  what: string,
  signal?: AbortSignal,
  params?: QueryParams,
): Promise<T> {
  const p = cleanParams(params);
  const data = await apiClient.get<unknown>(url, {
    tenantScoped: true,
    ...(signal ? { signal } : {}),
    ...(p !== undefined ? { params: p } : {}),
  });
  return parseResponse(schema, data, what);
}

export async function tenantList<T>(
  url: string,
  item: Schema<T>,
  what: string,
  signal?: AbortSignal,
  params?: QueryParams,
): Promise<T[]> {
  return tenantGet(url, array(item).required(), what, signal, params);
}

export function tenantPageSchema<T>(item: Schema<T>): Schema<Page<T>> {
  return object({
    items: array(item).required(),
    total: int(),
    page: int(),
    page_size: int(),
  });
}

export async function tenantPage<T>(
  url: string,
  schema: Schema<Page<T>>,
  query: TenantListQuery,
  what: string,
  signal?: AbortSignal,
): Promise<Page<T>> {
  return tenantGet(url, schema, what, signal, toListParams(query));
}

type Method = 'post' | 'put';

export async function tenantSend<T>(
  method: Method,
  url: string,
  body: unknown,
  schema: Schema<T>,
  what: string,
  idempotencyKey: string,
): Promise<T> {
  const data = await apiClient[method]<unknown>(url, body, { tenantScoped: true, idempotencyKey });
  return parseResponse(schema, data, what);
}

export const seg = (value: string) => encodeURIComponent(value);
