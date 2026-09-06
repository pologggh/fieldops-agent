import { describe, it, expect } from 'vitest';
import {
  buildDispatchPolicyAST,
  buildSLAPolicyAST,
  generateASTCodeDiff,
} from '../utils/policyAst';
import { DispatchPolicy, SLAPolicy } from '../types/admin';

describe('policyAst utility', () => {
  const mockDispatchPolicyV1: DispatchPolicy = {
    id: 1,
    version: 1,
    is_active: true,
    description: 'Initial dispatch policy',
    created_by: 'admin@fieldops.com',
    created_at: '2026-09-01T08:00:00Z',
    weights: {
      workload_weight: 25,
      capacity_weight: 20,
      sla_weight: 30,
      travel_weight: 15,
      overtime_penalty: 10,
    },
  };

  const mockDispatchPolicyV2: DispatchPolicy = {
    id: 2,
    version: 2,
    is_active: false,
    description: 'Updated SLA weight policy',
    created_by: 'admin@fieldops.com',
    created_at: '2026-09-02T08:00:00Z',
    weights: {
      workload_weight: 20,
      capacity_weight: 20,
      sla_weight: 40,
      travel_weight: 10,
      overtime_penalty: 10,
    },
  };

  it('generates valid AST object for dispatch policy', () => {
    const ast = buildDispatchPolicyAST(mockDispatchPolicyV1);
    expect(ast.astType).toBe('DispatchPolicyProgram');
    expect(ast.metadata.version).toBe(1);
    expect(ast.metadata.engine).toBe('FieldOpsMultiFactorRanker');
    expect(ast.spec.factors).toHaveLength(5);
  });

  it('generates valid AST object for SLA policy', () => {
    const mockSLA: SLAPolicy = {
      id: 1,
      version: 1,
      is_active: true,
      description: 'Standard SLA',
      created_by: 'admin',
      created_at: '2026-09-01T00:00:00Z',
      targets: {
        emergency: {
          response_minutes: 15,
          assignment_minutes: 30,
          service_start_minutes: 60,
          at_risk_threshold_minutes: 15,
        },
      },
    };

    const ast = buildSLAPolicyAST(mockSLA);
    expect(ast.astType).toBe('SLAPolicyProgram');
    expect(ast.tiers).toHaveLength(1);
    expect(ast.tiers[0].severity).toBe('CRITICAL_P0');
  });

  it('computes code diff lines between two AST versions with added and removed markers', () => {
    const ast1 = buildDispatchPolicyAST(mockDispatchPolicyV1);
    const ast2 = buildDispatchPolicyAST(mockDispatchPolicyV2);

    const { unifiedLines } = generateASTCodeDiff(ast1, ast2);
    expect(unifiedLines.length).toBeGreaterThan(0);

    const addedLines = unifiedLines.filter((l) => l.type === 'added');
    const removedLines = unifiedLines.filter((l) => l.type === 'removed');

    expect(addedLines.length).toBeGreaterThan(0);
    expect(removedLines.length).toBeGreaterThan(0);
  });
});
