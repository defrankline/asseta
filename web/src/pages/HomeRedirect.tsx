import { Navigate } from 'react-router';
import { buildNav } from '../navigation/buildNav';
import { IMPLEMENTED_PATHS, ROUTES } from '../navigation/routes';
import { useSession } from '../session/useSession';

/** Sends the user to the first implemented navigation entry of the active console. */
export function HomeRedirect() {
  const { me, mode, activeTenant, permissions } = useSession();
  const first = buildNav(mode, activeTenant, permissions, me).find((i) =>
    IMPLEMENTED_PATHS.has(i.path),
  );
  return <Navigate to={first?.path ?? ROUTES.myAccess} replace />;
}
