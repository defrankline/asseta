import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { meterService } from '../../../api/services/meterService';
import { MACHINE, makeCapture, makeException } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MeterCaptureDetailPage } from './MeterCaptureDetailPage';

const mocks = vi.hoisted(() => ({
  getCapture: vi.fn<typeof meterService.getCapture>(),
  listExceptions: vi.fn<typeof meterService.listExceptions>(),
}));
vi.mock('maplibre-gl', () => import('../../../test/maplibreMock'));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { getCapture: mocks.getCapture, listExceptions: mocks.listExceptions },
}));
vi.mock('../../../api/services/machineService', () => ({
  machineService: {
    list: vi.fn().mockResolvedValue({ items: [MACHINE], total: 1, page: 1, page_size: 200 }),
  },
}));

function open(id: string) {
  renderWithProviders(
    <Routes>
      <Route path="/tenant/meter-captures/:captureId" element={<MeterCaptureDetailPage />} />
    </Routes>,
    {
      tenantPermissions: ['tenant.meter.read', 'tenant.machine.read'],
      route: `/tenant/meter-captures/${id}`,
    },
  );
}

beforeEach(() => {
  mocks.listExceptions.mockResolvedValue({
    items: [makeException()],
    total: 1,
    page: 1,
    page_size: 100,
  });
});

describe('MeterCaptureDetailPage', () => {
  it('opens one reading by its id and asks only for that reading’s findings', async () => {
    const capture = makeCapture();
    mocks.getCapture.mockResolvedValue(capture);
    open(capture.id);
    expect(await screen.findByRole('heading', { name: /reading/i })).toBeInTheDocument();
    expect(mocks.getCapture).toHaveBeenCalledWith(capture.id, expect.any(AbortSignal));
    await waitFor(() => {
      expect(mocks.listExceptions).toHaveBeenCalledWith(
        { page: 1, page_size: 100, filters: { meter_capture_id: capture.id } },
        expect.any(AbortSignal),
      );
    });
  });

  it('says so when the reading cannot be opened', async () => {
    mocks.getCapture.mockRejectedValue(new Error('not found'));
    open('missing');
    expect(await screen.findByText(/Could not load this meter reading/)).toBeInTheDocument();
    expect(mocks.listExceptions).not.toHaveBeenCalled();
  });
});
