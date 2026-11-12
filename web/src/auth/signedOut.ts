import { ROUTES } from '../navigation/routes';

/** `?reason=` of the signed-out page, set by the app when it signs the person out itself. */
export const SIGNED_OUT_REASON = { accountDeleted: 'account-deleted' } as const;

/** Where Keycloak returns after the app signs out a person whose account was just deleted. */
export function accountDeletedPath(): string {
  return `${ROUTES.signedOut}?reason=${SIGNED_OUT_REASON.accountDeleted}`;
}
