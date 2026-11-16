import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { ReactElement } from 'react';
import { createRoutesFromElements, matchRoutes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from './AppRoutes';

/** Every console route the server returns (links, figures, menus) must open a real page, not the 404. */
const MODULES = resolve(__dirname, '../../../backend/src/asseta/modules');
const MODULE = resolve(MODULES, 'accountability');
const CASH = '/tenant/finance/cash';
const PETTY = '/tenant/finance/petty-cash';
const ID = '00000000-0000-4000-8000-000000000001';

const source = (file: string) => readFileSync(resolve(MODULE, file), 'utf8');

/** `RECORD_ROUTES` of links.py: record type -> list prefix. */
function recordRoutes(): [string, string][] {
  const text = source('links.py');
  const block = text.slice(text.indexOf('RECORD_ROUTES'), text.indexOf('def record_route'));
  return [...block.matchAll(/"([a-z_]+)": f?"([^"]+)"/g)].map((m): [string, string] => [
    m[1] ?? '',
    (m[2] ?? '').replace('{CASH}', CASH).replace('{PETTY}', PETTY),
  ]);
}

function pythonFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return pythonFiles(path);
    return name.endsWith('.py') ? [path] : [];
  });
}

/**
 * Tenant menu paths of the backend catalog: `MenuDef("key", S.TENANT, "Label", "/path", …)` and the
 * hours module's `("key", "Label", "/path", order, permission)` table.
 */
function tenantMenuPaths(): string[] {
  const found = new Set<string>();
  for (const file of pythonFiles(MODULES)) {
    const text = readFileSync(file, 'utf8');
    for (const m of text.matchAll(/MenuDef\(\s*"[^"]+",\s*S\.TENANT,\s*"[^"]*",\s*"([^"]+)"/g)) {
      found.add(m[1] ?? '');
    }
    for (const m of text.matchAll(/\("tenant\.[a-z_.]+", "[^"]*", "(\/tenant\/[^"]+)", \d+,/g)) {
      found.add(m[1] ?? '');
    }
  }
  return [...found].sort();
}

/** Paths named in sections.py: list routes, plain routes and the employee link. */
function figurePaths(): string[] {
  const found = new Set<string>();
  for (const m of source('sections.py').matchAll(/f?"((?:\/tenant|\{CASH\})[^"?]*)/g)) {
    found.add((m[1] ?? '').replace('{CASH}', CASH).replace('{b.staff_member_id}', ID));
  }
  return [...found];
}

function appRoutes() {
  const tree = AppRoutes() as ReactElement<{ children: ReactElement }>;
  return createRoutesFromElements(tree.props.children);
}

/** The deepest route the path lands on; `*` is the 404 page. */
function landing(path: string): string | undefined {
  const matches = matchRoutes(appRoutes(), path);
  return matches?.[matches.length - 1]?.route.path;
}

describe('routes the server returns', () => {
  it('reads the backend tables', () => {
    expect(recordRoutes().length).toBeGreaterThan(30);
    expect(figurePaths()).toContain('/tenant/accountability/pending-adjustments');
  });

  it.each(recordRoutes())('%s opens a page of its own', (_type, prefix) => {
    expect(landing(`${prefix}/${ID}`)).not.toBe('*');
    expect(landing(`${prefix}/${ID}`)).toBeDefined();
  });

  it('every tenant menu opens a page of its own', () => {
    const menus = tenantMenuPaths();
    expect(menus).toContain('/tenant/field/machine-report');
    expect(menus).toContain('/tenant/hours/credit-invoices');
    expect(menus).not.toContain('/tenant/hours/allocations');
    const missing = menus.filter((p) => {
      const at = landing(p);
      return at === undefined || at === '*';
    });
    expect(missing).toEqual([]);
  });

  it('every figure opens a list page', () => {
    const missing = figurePaths().filter((p) => {
      const at = landing(p);
      return at === undefined || at === '*';
    });
    expect(missing).toEqual([]);
  });

  it('the company closure menus open real pages', () => {
    const menus = readFileSync(
      resolve(__dirname, '../../../backend/src/asseta/modules/dataprotection/permissions.py'),
      'utf8',
    );
    for (const path of ['/tenant/company/close', '/platform/deletion-requests']) {
      expect(menus).toContain(`"${path}"`);
      expect(landing(path)).toBe(path);
    }
    expect(landing(`/platform/deletion-requests/${ID}`)).toBe(
      '/platform/deletion-requests/:requestId',
    );
  });

  it('the employee view and the lookup results exist', () => {
    expect(landing(`/tenant/staff/${ID}/accountability`)).toBe(
      '/tenant/staff/:staffId/accountability',
    );
    expect(landing('/tenant/lookup')).toBe('/tenant/lookup');
    expect(landing(`/tenant/customer-payments/${ID}`)).toBe('/tenant/customer-payments/:paymentId');
  });
});
