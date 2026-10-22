import { Navigate } from 'react-router';
import { buildNav, navItems } from '../navigation/buildNav';
import { IMPLEMENTED_PATHS, ROUTES } from '../navigation/routes';
import { useSession } from '../session/useSession';

/** Sends the user to the first implemented navigation entry of the active console (sign-in, console switch). */
export function HomeRedirect() {
  const { me, mode, activeTenant } = useSession();
  // The first item of the first group (each console's Overview) is the landing page.
  const first = navItems(buildNav(mode, activeTenant, me)).find((i) =>
    IMPLEMENTED_PATHS.has(i.path),
  );
  return <Navigate to={first?.path ?? ROUTES.myAccess} replace />;
}
