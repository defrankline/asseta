import { apiClient } from '../client';
import type { PlatformDashboardDto } from '../types';
import { parseResponse } from '../validation';
import { dashboardSchema } from './billingSchemas';

export const platformDashboardService = {
  /** GET /platform/dashboard (getPlatformDashboard). */
  async get(signal?: AbortSignal): Promise<PlatformDashboardDto> {
    const data = await apiClient.get<unknown>(
      '/platform/dashboard',
      signal ? { signal } : undefined,
    );
    return parseResponse(dashboardSchema, data, 'platform dashboard');
  },
};
