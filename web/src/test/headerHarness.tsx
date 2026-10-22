import { NotificationBell } from '../notifications/center/NotificationBell';
import { ConnectionIndicator } from '../realtime/ConnectionIndicator';

/** The realtime pieces of the app header (indicator + bell), without auth / theme providers. */
export function AppHeaderTestBar() {
  return (
    <header>
      <ConnectionIndicator />
      <NotificationBell />
    </header>
  );
}
