import axios, {
  isAxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';
import { appConfig } from '../config/env';
import { ApiError, toApiError } from './ApiError';
import { newUuid } from './ids';
import { requestContext, type RequestContext } from './requestContext';

declare module 'axios' {
  interface AxiosRequestConfig {
    /** Adds `X-Tenant-ID` from the active tenant; fails fast if no tenant is selected. */
    tenantScoped?: boolean;
    /** Sent as `Idempotency-Key`; required for POST/PUT/PATCH/DELETE. */
    idempotencyKey?: string;
  }
}

export const HEADER = {
  authorization: 'Authorization',
  tenant: 'X-Tenant-ID',
  correlation: 'X-Correlation-ID',
  idempotency: 'Idempotency-Key',
} as const;

/** Error codes meaning the caller's managed-service access to the tenant is gone. */
export const MANDATE_LOST_CODES: ReadonlySet<string> = new Set([
  'MANDATE_REQUIRED',
  'MANDATE_ENDED',
]);

const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

async function decorateRequest(
  config: InternalAxiosRequestConfig,
  ctx: RequestContext,
): Promise<InternalAxiosRequestConfig> {
  config.headers.set(HEADER.correlation, newUuid());

  const token = await ctx.getAccessToken();
  if (token !== null) config.headers.set(HEADER.authorization, `Bearer ${token}`);

  if (config.tenantScoped === true) {
    const tenantId = ctx.getActiveTenantId();
    if (tenantId === null) {
      throw new ApiError({
        status: null,
        code: 'tenant_not_selected',
        message: 'Select a tenant before performing this action.',
        correlationId: null,
      });
    }
    config.headers.set(HEADER.tenant, tenantId);
  }

  const method = (config.method ?? 'get').toLowerCase();
  if (MUTATING_METHODS.has(method)) {
    if (config.idempotencyKey === undefined || config.idempotencyKey === '') {
      throw new ApiError({
        status: null,
        code: 'idempotency_key_required',
        message: `Idempotency-Key is required for ${method.toUpperCase()} requests.`,
        correlationId: null,
      });
    }
    config.headers.set(HEADER.idempotency, config.idempotencyKey);
  }
  return config;
}

function tenantHeader(error: unknown): string | null {
  if (!isAxiosError(error)) return null;
  const value: unknown = error.config?.headers.get(HEADER.tenant);
  return typeof value === 'string' ? value : null;
}

/** Build an Axios instance with Asseta headers and error normalisation. Exported for tests. */
export function createHttpClient(baseURL: string, ctx: RequestContext): AxiosInstance {
  const instance = axios.create({
    baseURL,
    timeout: 30_000,
    headers: { Accept: 'application/json' },
  });
  instance.interceptors.request.use((config) => decorateRequest(config, ctx));
  instance.interceptors.response.use(undefined, (error: unknown) => {
    const apiError = toApiError(error);
    if (apiError.status === 401) ctx.onUnauthorized();
    if (MANDATE_LOST_CODES.has(apiError.code)) {
      ctx.onMandateLost(tenantHeader(error), apiError.code);
    }
    return Promise.reject(apiError);
  });
  return instance;
}

/** The single application Axios instance. Only the API layer may import it. */
export const http: AxiosInstance = createHttpClient(appConfig.apiBaseUrl, requestContext);

export type QueryParams = Record<string, string | number | boolean | undefined>;

export interface RequestOptions {
  params?: QueryParams;
  signal?: AbortSignal;
  tenantScoped?: boolean;
  /** Extra HTTP statuses to treat as success (e.g. 503 for readiness probes). */
  acceptStatuses?: readonly number[];
}

export interface MutationOptions extends RequestOptions {
  idempotencyKey: string;
}

function toConfig(options: RequestOptions | undefined): AxiosRequestConfig {
  const accept = options?.acceptStatuses ?? [];
  const config: AxiosRequestConfig = {
    validateStatus: (s) => (s >= 200 && s < 300) || accept.includes(s),
  };
  if (options?.params !== undefined) config.params = options.params;
  if (options?.signal !== undefined) config.signal = options.signal;
  if (options?.tenantScoped !== undefined) config.tenantScoped = options.tenantScoped;
  return config;
}

function toMutationConfig(options: MutationOptions): AxiosRequestConfig {
  return { ...toConfig(options), idempotencyKey: options.idempotencyKey };
}

export interface ApiClient {
  get<T>(url: string, options?: RequestOptions): Promise<T>;
  post<T>(url: string, body: unknown, options: MutationOptions): Promise<T>;
  put<T>(url: string, body: unknown, options: MutationOptions): Promise<T>;
  patch<T>(url: string, body: unknown, options: MutationOptions): Promise<T>;
  delete<T = void>(url: string, options: MutationOptions): Promise<T>;
}

/** Typed helpers over an Axios instance; resolve with the response body. */
export function createApiClient(instance: AxiosInstance): ApiClient {
  return {
    async get<T>(url: string, options?: RequestOptions) {
      return (await instance.get<T>(url, toConfig(options))).data;
    },
    async post<T>(url: string, body: unknown, options: MutationOptions) {
      return (await instance.post<T>(url, body, toMutationConfig(options))).data;
    },
    async put<T>(url: string, body: unknown, options: MutationOptions) {
      return (await instance.put<T>(url, body, toMutationConfig(options))).data;
    },
    async patch<T>(url: string, body: unknown, options: MutationOptions) {
      return (await instance.patch<T>(url, body, toMutationConfig(options))).data;
    },
    async delete<T = void>(url: string, options: MutationOptions) {
      return (await instance.delete<T>(url, toMutationConfig(options))).data;
    },
  };
}

export const apiClient: ApiClient = createApiClient(http);

/** Convert a ListQuery-like object into query params, dropping empty values. */
export function toListParams(query: {
  page: number;
  page_size: number;
  sort?: string | undefined;
  q?: string | undefined;
  filters?: Readonly<Record<string, string | undefined>> | undefined;
}): QueryParams {
  const params: QueryParams = { page: query.page, page_size: query.page_size };
  if (query.sort !== undefined && query.sort !== '') params.sort = query.sort;
  if (query.q !== undefined && query.q.trim() !== '') params.q = query.q.trim();
  for (const [k, v] of Object.entries(query.filters ?? {})) {
    if (v !== undefined && v !== '') params[k] = v;
  }
  return params;
}
