// @vitest-environment node
import { ESLint } from 'eslint';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';
import { describe, expect, it } from 'vitest';
import { DROPDOWN_RULES } from '../../eslint/dropdownRules.js';

const WEB_ROOT = fileURLToPath(new URL('../..', import.meta.url));

/** Lints a snippet with only the dropdown guard (no type information needed). */
async function guardMessages(code: string): Promise<string[]> {
  const eslint = new ESLint({
    cwd: WEB_ROOT,
    overrideConfigFile: true,
    overrideConfig: [
      {
        files: ['**/*.tsx'],
        languageOptions: {
          parser: tseslint.parser,
          parserOptions: { ecmaFeatures: { jsx: true } },
        },
        rules: { 'no-restricted-syntax': ['error', ...DROPDOWN_RULES] },
      },
    ],
  });
  const [result] = await eslint.lintText(code, { filePath: 'src/pages/Fixture.tsx' });
  return (result?.messages ?? []).map((m) => m.message);
}

describe('ESLint dropdown guard (no TextField + MenuItem for backend data)', () => {
  it('fails on <MenuItem> mapped from fetched data', async () => {
    const messages = await guardMessages(`
      export const F = ({ categories }) => (
        <TextField select>
          {(categories.data ?? []).map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
          {sites.map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
        </TextField>
      );`);
    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatch(/AsyncAutocomplete/);
  });

  it('fails on FormikSelectField / StaticSelectFilter options that are not ALL_CAPS constants', async () => {
    const messages = await guardMessages(`
      export const F = () => (
        <>
          <FormikSelectField name="tenant_id" options={tenantOptions} />
          <FormikSelectField name="c" options={categories.map((c) => ({ value: c.id, label: c.name }))} />
          <FormikSelectField name="s" options={[none, ...list]} />
          <StaticSelectFilter label="x" value="" onChange={f} options={rows} />
        </>
      );`);
    expect(messages).toHaveLength(4);
    expect(messages.every((m) => m.includes('ALL_CAPS'))).toBe(true);
  });

  it('allows static ALL_CAPS enums, static lookups and the async autocomplete', async () => {
    const messages = await guardMessages(`
      export const F = ({ state }) => (
        <>
          <TextField select>
            {STATUS_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
          </TextField>
          <FormikSelectField name="kind" options={KIND_OPTIONS} />
          <FormikSelectField name="state" options={STATE_TARGET_OPTIONS[state]} />
          <AsyncAutocomplete label="Machine" fetchOptions={search} value={null} onChange={f} />
        </>
      );`);
    expect(messages).toEqual([]);
  });

  it('is enabled for source files by the project ESLint config', async () => {
    const eslint = new ESLint({ cwd: WEB_ROOT });
    const config = (await eslint.calculateConfigForFile('src/pages/Example.tsx')) as {
      rules: Record<string, unknown[]>;
    };
    const entries = config.rules['no-restricted-syntax'] ?? [];
    expect(entries.slice(1)).toEqual(expect.arrayContaining([...DROPDOWN_RULES]));
  });
});
