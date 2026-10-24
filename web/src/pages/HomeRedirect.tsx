import { Navigate } from 'react-router';
import { buildNav, navItems } from '../navigation/buildNav';
import { IMPLEMENTED_PATHS, ROUTES } from '../navigation/routes';
import { useSession } from '../session/useSession';
import { isFieldUser } from './tenant/field/fieldWork';

/** Sends the user to the first implemented navigation entry of the active console (sign-in, console switch). */
export function HomeRedirect() {
  const { me, mode, activeTenant, hasPermission } = useSession();
  const items = navItems(buildNav(mode, activeTenant, me));
  // Field users (supervisors without office oversight) start on My jobs; everyone else on the first
  // item of the first group (each console's Overview).
  const fieldHome =
    mode.kind === 'tenant' && isFieldUser(hasPermission)
      ? items.find((i) => i.path === ROUTES.fieldJobs)
      : undefined;
  const first = fieldHome ?? items.find((i) => IMPLEMENTED_PATHS.has(i.path));
  return <Navigate to={first?.path ?? ROUTES.myAccess} replace />;
}
