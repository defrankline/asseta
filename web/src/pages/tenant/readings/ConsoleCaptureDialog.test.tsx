import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../../api/ApiError';
import type { meterService } from '../../../api/services/meterService';
import type { policyService } from '../../../api/services/policyService';
import { makeCapture, makeJob } from '../../../test/jobFixtures';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { ConsoleCaptureDialog } from './ConsoleCaptureDialog';

const mocks = vi.hoisted(() => ({
  submitCapture: vi.fn<typeof meterService.submitCapture>(),
  upload: vi.fn<typeof meterService.upload>(),
  effective: vi.fn<typeof policyService.effective>(),
}));
vi.mock('../../../api/services/meterService', () => ({
  meterService: { submitCapture: mocks.submitCapture, upload: mocks.upload },
}));
vi.mock('../../../api/services/policyService', () => ({
  policyService: { effective: mocks.effective },
}));

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const FIX_TIME = Date.parse('2026-10-21T15:00:00Z');

type Outcome =
  { fix: { latitude: number; longitude: number; accuracy: number } } | { code: number };

function mockGeolocation(outcome: Outcome) {
  const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((ok, fail) => {
    if ('fix' in outcome) {
      ok({ coords: outcome.fix, timestamp: FIX_TIME } as unknown as GeolocationPosition);
    } else {
      fail?.({ code: outcome.code, message: 'x' } as GeolocationPositionError);
    }
  });
  Object.defineProperty(navigator, 'geolocation', {
    value: { getCurrentPosition },
    configurable: true,
  });
  return getCurrentPosition;
}

beforeEach(() => {
  mocks.effective.mockResolvedValue({
    policy_type: 'METER_CAPTURE',
    version_stamp: 'MC:P1+T2',
    values: {
      opening_mode: 'AUTOMATIC',
      closing_mode: 'MANUAL',
      manual_photo_required: false,
      gps_enforcement: 'SOFT',
      gps_max_accuracy_m: 50,
      gps_max_age_seconds: 120,
    },
  });
  mocks.submitCapture.mockResolvedValue({ capture: makeCapture(), findings: [] });
});
afterEach(() => {
  Reflect.deleteProperty(navigator, 'geolocation');
});

function render() {
  renderWithProviders(
    <ConsoleCaptureDialog
      job={makeJob({ status: 'IN_PROGRESS' })}
      kind="CLOSING"
      onClose={vi.fn()}
      onRecorded={vi.fn()}
    />,
    { tenantPermissions: ['tenant.job.read', 'tenant.meter.capture', 'tenant.policy.read'] },
  );
}

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
  await user.click(await screen.findByRole('option', { name: 'Manual (numeric entry)' }));
  await user.type(screen.getByRole('textbox', { name: /Meter reading/ }), '1208.8');
}

describe('ConsoleCaptureDialog', () => {
  it('shows the required mode and keeps one capture id across retries with the real fix', async () => {
    const user = userEvent.setup();
    const geo = mockGeolocation({ fix: { latitude: -6.8, longitude: 39.28, accuracy: 9 } });
    mocks.submitCapture.mockRejectedValueOnce(
      new ApiError({
        status: null,
        code: 'network_error',
        message: 'Network error.',
        correlationId: null,
      }),
    );
    render();
    expect(await screen.findByText('Policy requires Manual for this reading')).toBeInTheDocument();
    expect(await screen.findByText('GPS fix')).toBeInTheDocument();
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    expect(await screen.findByText(/Network error/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    await waitFor(() => {
      expect(mocks.submitCapture).toHaveBeenCalledTimes(2);
    });
    const [first, second] = mocks.submitCapture.mock.calls;
    expect(first?.[0].id).toMatch(UUID);
    expect(second?.[0].id).toBe(first?.[0].id);
    expect(second?.[1]).toBe(first?.[1]);
    expect(first?.[0]).toMatchObject({
      kind: 'CLOSING',
      capture_mode: 'MANUAL',
      reading: '1208.8',
      device_id: 'web-console',
      photo_attachment_id: null,
      ocr_value: null,
      gps: {
        status: 'FIX',
        latitude: -6.8,
        longitude: 39.28,
        accuracy_m: 9,
        captured_at: new Date(FIX_TIME).toISOString(),
        provider: 'browser',
      },
    });
    expect(geo).toHaveBeenCalledTimes(1);
    expect(geo.mock.calls[0]?.[2]).toMatchObject({ enableHighAccuracy: true, maximumAge: 0 });
  });

  it.each([
    [1, 'PERMISSION_DENIED', 'Permission denied'],
    [2, 'NO_FIX', 'No fix'],
    [3, 'TIMEOUT', 'Timed out'],
  ] as const)('submits error code %i as %s without coordinates', async (code, status, label) => {
    const user = userEvent.setup();
    mockGeolocation({ code });
    render();
    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.getByText(/No coordinates will be sent/)).toBeInTheDocument();
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    await waitFor(() => {
      expect(mocks.submitCapture).toHaveBeenCalledTimes(1);
    });
    const gps = mocks.submitCapture.mock.calls[0]?.[0].gps;
    expect(gps).toEqual({ status, provider: 'browser' });
    expect(gps).not.toHaveProperty('latitude');
    expect(gps).not.toHaveProperty('longitude');
  });

  it('reports DISABLED when the browser has no geolocation', async () => {
    const user = userEvent.setup();
    render();
    expect(await screen.findByText('Location disabled')).toBeInTheDocument();
    await fill(user);
    await user.click(screen.getByRole('button', { name: 'Submit reading' }));
    await waitFor(() => {
      expect(mocks.submitCapture.mock.calls[0]?.[0].gps).toEqual({
        status: 'DISABLED',
        provider: 'browser',
      });
    });
  });

  it('warns when the chosen mode differs from the policy', async () => {
    const user = userEvent.setup();
    mockGeolocation({ code: 1 });
    render();
    await screen.findByText('Policy requires Manual for this reading');
    await user.click(screen.getByRole('combobox', { name: /Capture mode/ }));
    await user.click(await screen.findByRole('option', { name: /Automatic/ }));
    expect(await screen.findByText(/This differs from the policy/)).toBeInTheDocument();
  });
});
