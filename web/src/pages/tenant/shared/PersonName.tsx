import { useEffect, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useSession } from '../../../session/useSession';
import { shortId } from './financeDisplay';
import { lookupPersonName } from './personDirectory';

interface PersonNameProps {
  userId: string | null;
  /** The name the server sent with the record (`*_by_name`); used as is, no directory lookup. */
  name?: string | null | undefined;
  /** Shown when `userId` is null (e.g. "policy (auto)"). */
  empty?: string;
}

/** A colleague's display name on a record ("You" for the signed-in user; the short id until resolved). */
export function PersonName({ userId, name: given = null, empty = '—' }: PersonNameProps) {
  const { me, activeTenant, hasPermission } = useSession();
  const tenantId = activeTenant?.tenant_id ?? null;
  const canResolve = hasPermission(PERMISSIONS.tenantDirectoryRead);
  const [resolved, setResolved] = useState<{ key: string; name: string | null } | null>(null);
  const key = `${tenantId ?? ''}:${userId ?? ''}`;
  const isMe = userId !== null && userId === me?.user_id;
  const named = given !== null && given !== '';

  useEffect(() => {
    if (userId === null || tenantId === null || isMe || named || !canResolve) return undefined;
    let live = true;
    void lookupPersonName(tenantId, userId).then((name) => {
      if (live) setResolved({ key, name });
    });
    return () => {
      live = false;
    };
  }, [key, userId, tenantId, isMe, named, canResolve]);

  if (userId === null) return <>{empty}</>;
  if (isMe) return <>You</>;
  if (named) return <>{given}</>;
  const name = resolved?.key === key ? resolved.name : null;
  return <>{name ?? shortId(userId)}</>;
}
