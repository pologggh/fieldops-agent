import { DispatchPolicy, SLAPolicy, DispatchWeights, SLATargetTier } from '../types/admin';

export interface ASTDiffLine {
  lineNumber: number;
  type: 'same' | 'added' | 'removed' | 'modified';
  prefix: ' ' | '+' | '-' | '~';
  content: string;
  indent: number;
}

/**
 * Builds an Abstract Syntax Tree (AST) structure for Dispatch Policies
 */
export function buildDispatchPolicyAST(policy: DispatchPolicy) {
  return {
    $schema: 'https://fieldops.cn/schemas/dispatch-ast-v2.json',
    astType: 'DispatchPolicyProgram',
    metadata: {
      policyId: `dp-${policy.id}`,
      version: policy.version,
      state: policy.is_active ? 'ACTIVE' : 'INACTIVE',
      engine: 'FieldOpsMultiFactorRanker',
      author: policy.created_by || 'system',
      createdAt: policy.created_at,
    },
    spec: {
      evaluationMode: 'WEIGHTED_SUM',
      sumConstraint: {
        type: 'InvariantConstraint',
        targetSum: 100,
        enforced: true,
      },
      factors: [
        {
          id: 'workload_weight',
          name: '工作负载因子',
          weight: policy.weights.workload_weight,
          normalizedFraction: policy.weights.workload_weight / 100,
          penaltyScale: 1.0,
        },
        {
          id: 'capacity_weight',
          name: '网格容量因子',
          weight: policy.weights.capacity_weight,
          normalizedFraction: policy.weights.capacity_weight / 100,
          penaltyScale: 1.0,
        },
        {
          id: 'sla_weight',
          name: '时效紧迫因子',
          weight: policy.weights.sla_weight,
          normalizedFraction: policy.weights.sla_weight / 100,
          penaltyScale: 1.2,
        },
        {
          id: 'travel_weight',
          name: '通勤成本因子',
          weight: policy.weights.travel_weight,
          normalizedFraction: policy.weights.travel_weight / 100,
          penaltyScale: 0.8,
        },
        {
          id: 'overtime_penalty',
          name: '超时惩罚因子',
          weight: policy.weights.overtime_penalty,
          normalizedFraction: policy.weights.overtime_penalty / 100,
          penaltyScale: 1.5,
        },
      ],
    },
  };
}

/**
 * Builds an Abstract Syntax Tree (AST) structure for SLA Policies
 */
export function buildSLAPolicyAST(policy: SLAPolicy) {
  return {
    $schema: 'https://fieldops.cn/schemas/sla-ast-v2.json',
    astType: 'SLAPolicyProgram',
    metadata: {
      policyId: `sla-${policy.id}`,
      version: policy.version,
      state: policy.is_active ? 'ACTIVE' : 'INACTIVE',
      engine: 'FieldOpsEscalationEngine',
      author: policy.created_by || 'system',
      createdAt: policy.created_at,
    },
    tiers: Object.entries(policy.targets || {}).map(([tierName, tierData]) => ({
      tier: tierName.toUpperCase(),
      severity: tierName === 'emergency' ? 'CRITICAL_P0' : tierName === 'high' ? 'HIGH_P1' : 'STANDARD',
      thresholds: {
        responseMinutes: tierData.response_minutes,
        assignmentMinutes: tierData.assignment_minutes,
        serviceStartMinutes: tierData.service_start_minutes,
        atRiskMinutes: tierData.at_risk_threshold_minutes,
      },
      escalationAction: tierName === 'emergency' ? 'NOTIFY_DISPATCHER_IMMEDIATE' : 'ALERT_EXPIRING_QUEUE',
    })),
  };
}

/**
 * Compares two AST objects and produces line-by-line diff
 */
export function generateASTCodeDiff(
  activeAST: any,
  targetAST: any
): { activeLines: ASTDiffLine[]; targetLines: ASTDiffLine[]; unifiedLines: ASTDiffLine[] } {
  const activeStr = activeAST ? JSON.stringify(activeAST, null, 2) : '';
  const targetStr = targetAST ? JSON.stringify(targetAST, null, 2) : '';

  const activeRaw = activeStr ? activeStr.split('\n') : [];
  const targetRaw = targetStr ? targetStr.split('\n') : [];

  const unifiedLines: ASTDiffLine[] = [];
  const activeLines: ASTDiffLine[] = [];
  const targetLines: ASTDiffLine[] = [];

  const maxLen = Math.max(activeRaw.length, targetRaw.length);

  for (let i = 0; i < maxLen; i++) {
    const act = activeRaw[i] !== undefined ? activeRaw[i] : null;
    const tgt = targetRaw[i] !== undefined ? targetRaw[i] : null;

    if (act !== null && tgt !== null) {
      if (act === tgt) {
        unifiedLines.push({
          lineNumber: i + 1,
          type: 'same',
          prefix: ' ',
          content: tgt,
          indent: tgt.search(/\S|$/),
        });
        activeLines.push({
          lineNumber: i + 1,
          type: 'same',
          prefix: ' ',
          content: act,
          indent: act.search(/\S|$/),
        });
        targetLines.push({
          lineNumber: i + 1,
          type: 'same',
          prefix: ' ',
          content: tgt,
          indent: tgt.search(/\S|$/),
        });
      } else {
        // Line modified between active and target
        unifiedLines.push({
          lineNumber: i + 1,
          type: 'removed',
          prefix: '-',
          content: act,
          indent: act.search(/\S|$/),
        });
        unifiedLines.push({
          lineNumber: i + 1,
          type: 'added',
          prefix: '+',
          content: tgt,
          indent: tgt.search(/\S|$/),
        });

        activeLines.push({
          lineNumber: i + 1,
          type: 'removed',
          prefix: '-',
          content: act,
          indent: act.search(/\S|$/),
        });
        targetLines.push({
          lineNumber: i + 1,
          type: 'added',
          prefix: '+',
          content: tgt,
          indent: tgt.search(/\S|$/),
        });
      }
    } else if (act !== null && tgt === null) {
      unifiedLines.push({
        lineNumber: i + 1,
        type: 'removed',
        prefix: '-',
        content: act,
        indent: act.search(/\S|$/),
      });
      activeLines.push({
        lineNumber: i + 1,
        type: 'removed',
        prefix: '-',
        content: act,
        indent: act.search(/\S|$/),
      });
    } else if (act === null && tgt !== null) {
      unifiedLines.push({
        lineNumber: i + 1,
        type: 'added',
        prefix: '+',
        content: tgt,
        indent: tgt.search(/\S|$/),
      });
      targetLines.push({
        lineNumber: i + 1,
        type: 'added',
        prefix: '+',
        content: tgt,
        indent: tgt.search(/\S|$/),
      });
    }
  }

  return { activeLines, targetLines, unifiedLines };
}
