import type { ClientMandateDto, MandateCloseIn } from '../types';
import { clientMandateSchema } from './mandateSchemas';
import { seg, tenantGet, tenantSend } from './tenantRequest';

const base = '/tenant/managed-service';

/** Client side of the managed service: see and revoke the mandate held over this tenant. */
export const managedServiceService = {
  /** GET /tenant/managed-service (getClientMandate). */
  get(signal?: AbortSignal): Promise<ClientMandateDto> {
    return tenantGet(base, clientMandateSchema, 'managed service', signal);
  },
  /** POST /tenant/managed-service/{id}/revoke. MANDATE_SELF_REVOKE when acting under it. */
  revoke(
    mandateId: string,
    body: MandateCloseIn,
    idempotencyKey: string,
  ): Promise<ClientMandateDto> {
    return tenantSend(
      'post',
      `${base}/${seg(mandateId)}/revoke`,
      body,
      clientMandateSchema,
      'managed service',
      idempotencyKey,
    );
  },
};
