import { describe, expect, it } from 'vitest';
import { makeCase, makeCaseSignal, makeRiskSignal, RULE_EVIDENCE } from '../../test/caseFixtures';
import { anomalyCaseSchema, caseSignalSchema, riskSignalSchema } from './intelligenceSchemas';

describe('intelligence schemas accept every rule and case source of the contract', () => {
  it('loads DEC-031 Phase 2 signals (engine running without work, fuel above the norm)', () => {
    for (const rule of ['ENGINE_RUNNING_WITHOUT_WORK', 'MACHINE_FUEL_ABOVE_NORM'] as const) {
      expect(
        riskSignalSchema.isValidSync(
          makeRiskSignal({ rule_code: rule, evidence: { ...RULE_EVIDENCE[rule] } }),
        ),
      ).toBe(true);
      expect(caseSignalSchema.isValidSync(makeCaseSignal({ code: rule }))).toBe(true);
    }
    expect(
      riskSignalSchema.isValidSync(makeRiskSignal({ rule_code: 'UNEXPLAINED_ENGINE_HOURS' })),
    ).toBe(true);
  });

  it('loads cases fed by cash variances and revenue differences', () => {
    expect(
      caseSignalSchema.isValidSync(
        makeCaseSignal({ source_type: 'REVENUE_DIFFERENCE', code: 'REVENUE_DIFFERENCE' }),
      ),
    ).toBe(true);
    expect(
      caseSignalSchema.isValidSync(
        makeCaseSignal({ source_type: 'CASH_VARIANCE', code: 'CASH_VARIANCE' }),
      ),
    ).toBe(true);
    expect(anomalyCaseSchema.isValidSync(makeCase())).toBe(true);
  });
});
