import React, { useState, useMemo } from 'react';
import {
  X,
  ArrowRight,
  CheckCircle2,
  Code2,
  Table,
  Copy,
  Check,
  FileCode,
  Layers,
} from 'lucide-react';
import { DispatchPolicy, DispatchWeights, SLAPolicy, SLATargetTier } from '../../types/admin';
import { formatDateTimeZh } from '../../utils/dateTime';
import {
  buildDispatchPolicyAST,
  buildSLAPolicyAST,
  generateASTCodeDiff,
} from '../../utils/policyAst';

interface PolicyDiffModalProps {
  isOpen: boolean;
  type: 'dispatch' | 'sla';
  activePolicy: DispatchPolicy | SLAPolicy | null;
  targetPolicy: DispatchPolicy | SLAPolicy | null;
  onClose: () => void;
  onActivate?: () => void;
  isActivating?: boolean;
}

export const PolicyDiffModal: React.FC<PolicyDiffModalProps> = ({
  isOpen,
  type,
  activePolicy,
  targetPolicy,
  onClose,
  onActivate,
  isActivating = false,
}) => {
  const [diffMode, setDiffMode] = useState<'table' | 'ast'>('table');
  const [copiedAST, setCopiedAST] = useState(false);

  if (!isOpen || !targetPolicy) return null;

  const isCurrentActive = activePolicy?.id === targetPolicy.id;

  const getFactorZh = (key: string) => {
    switch (key) {
      case 'workload_weight':
        return '工作负载权重 (Workload)';
      case 'capacity_weight':
        return '服务网格容量权重 (Capacity)';
      case 'sla_weight':
        return '服务时效权重 (SLA Fit)';
      case 'travel_weight':
        return '路程成本权重 (Travel)';
      case 'overtime_penalty':
        return '超时惩罚因子 (Overtime Penalty)';
      default:
        return key;
    }
  };

  const getMetricZh = (key: string) => {
    switch (key) {
      case 'response_minutes':
        return '响应确认时限';
      case 'assignment_minutes':
        return '调度派单时限';
      case 'arrival_minutes':
        return '到场签到时限';
      case 'resolution_minutes':
        return '竣工验收时限';
      default:
        return key;
    }
  };

  const getTierZh = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'emergency':
        return '紧急故障 (P0 / Emergency)';
      case 'high':
        return '高优先级 (P1 / High)';
      case 'medium':
        return '普通报修 (P2 / Medium)';
      case 'low':
        return '低优先级巡检 (P3 / Low)';
      default:
        return tier;
    }
  };

  // Generate AST representations
  const activeAST = useMemo(() => {
    if (!activePolicy) return null;
    return type === 'dispatch'
      ? buildDispatchPolicyAST(activePolicy as DispatchPolicy)
      : buildSLAPolicyAST(activePolicy as SLAPolicy);
  }, [activePolicy, type]);

  const targetAST = useMemo(() => {
    if (!targetPolicy) return null;
    return type === 'dispatch'
      ? buildDispatchPolicyAST(targetPolicy as DispatchPolicy)
      : buildSLAPolicyAST(targetPolicy as SLAPolicy);
  }, [targetPolicy, type]);

  const { unifiedLines } = useMemo(() => {
    return generateASTCodeDiff(activeAST, targetAST);
  }, [activeAST, targetAST]);

  const handleCopyAST = () => {
    if (!targetAST) return;
    navigator.clipboard.writeText(JSON.stringify(targetAST, null, 2));
    setCopiedAST(true);
    setTimeout(() => setCopiedAST(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="text-lg font-bold text-slate-900">
                策略版本差异对比：目标版本 v{targetPolicy.version} vs 当前生效 (v
                {activePolicy?.version ?? '?'})
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                {type === 'dispatch' ? '智能派单规则' : 'SLA 服务时效标准'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              核对策略多因子权重、AST 语法树规则定义及服务时效阈值变更差异。
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* View Mode Segmented Controls */}
            <div className="flex items-center bg-slate-200/80 p-0.5 rounded-xl text-xs font-semibold">
              <button
                type="button"
                onClick={() => setDiffMode('table')}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  diffMode === 'table'
                    ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Table className="w-3.5 h-3.5" />
                <span>参数对比表</span>
              </button>
              <button
                type="button"
                onClick={() => setDiffMode('ast')}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  diffMode === 'ast'
                    ? 'bg-indigo-600 text-white shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>AST 语法树与代码比对</span>
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {diffMode === 'table' ? (
            <>
              {type === 'dispatch' && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                    派单算法评分权重差异表
                  </h4>
                  <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600">
                        <tr>
                          <th className="px-4 py-3">权重考量因子</th>
                          <th className="px-4 py-3">当前生效 (v{activePolicy?.version ?? '?'})</th>
                          <th className="px-4 py-3">目标对比版本 (v{targetPolicy.version})</th>
                          <th className="px-4 py-3">权重调整差值</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 font-mono text-xs">
                        {Object.entries((targetPolicy as DispatchPolicy).weights).map(
                          ([key, targetVal]) => {
                            const activeVal =
                              (activePolicy as DispatchPolicy)?.weights?.[
                                key as keyof DispatchWeights
                              ] ?? 0;
                            const delta = targetVal - activeVal;
                            return (
                              <tr key={key} className={delta !== 0 ? 'bg-amber-50/40' : ''}>
                                <td className="px-4 py-3 font-medium text-slate-800 font-sans">
                                  {getFactorZh(key)}
                                </td>
                                <td className="px-4 py-3 text-slate-600">{activeVal}%</td>
                                <td className="px-4 py-3 font-semibold text-slate-900">
                                  {targetVal}%
                                </td>
                                <td className="px-4 py-3">
                                  {delta > 0 ? (
                                    <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">
                                      +{delta}%
                                    </span>
                                  ) : delta < 0 ? (
                                    <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded">
                                      {delta}%
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">0% (无变化)</span>
                                  )}
                                </td>
                              </tr>
                            );
                          }
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {type === 'sla' && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                    SLA 服务时效阶梯阈值对比 (单位：分钟)
                  </h4>
                  <div className="space-y-4">
                    {Object.entries((targetPolicy as SLAPolicy).targets).map(([tier, targets]) => {
                      const activeTargets = (activePolicy as SLAPolicy)?.targets?.[tier];
                      return (
                        <div
                          key={tier}
                          className="border border-slate-200 rounded-xl p-4 bg-slate-50/50"
                        >
                          <h5 className="font-bold text-sm text-indigo-900 mb-2">
                            {getTierZh(tier)}
                          </h5>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                            {Object.entries(targets).map(([metric, val]) => {
                              const activeVal =
                                activeTargets?.[metric as keyof SLATargetTier] ?? 0;
                              const changed = val !== activeVal;
                              return (
                                <div
                                  key={metric}
                                  className={`p-2.5 rounded-lg border ${
                                    changed
                                      ? 'bg-amber-50 border-amber-200'
                                      : 'bg-white border-slate-200'
                                  }`}
                                >
                                  <div className="text-[11px] text-slate-500 font-medium">
                                    {getMetricZh(metric)}
                                  </div>
                                  <div className="flex items-center gap-1.5 mt-1">
                                    <span className="line-through text-slate-400 font-mono">
                                      {activeVal} 分钟
                                    </span>
                                    <ArrowRight className="w-3 h-3 text-slate-400" />
                                    <span className="font-bold text-slate-900 font-mono">
                                      {val} 分钟
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            /* AST & Code Syntax Tree Diff View */
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-indigo-600" />
                  <span className="text-xs font-bold text-slate-800">
                    抽象语法树规范 (AST Code Diff) · v{activePolicy?.version ?? '0'} ➔ v
                    {targetPolicy.version}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">
                      + 目标新增属性
                    </span>
                    <span className="inline-flex items-center gap-1 text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded">
                      - 原版移除属性
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleCopyAST}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors cursor-pointer"
                  >
                    {copiedAST ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>已复制</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-500" />
                        <span>复制 AST JSON</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Code Diff Display Window */}
              <div className="bg-slate-950 rounded-2xl border border-slate-800 shadow-inner overflow-hidden font-mono text-xs">
                <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-slate-400 text-[11px]">
                  <span>policy_spec.ast.json</span>
                  <span>编码: UTF-8 · 引擎: FieldOps AST Engine</span>
                </div>
                <div className="p-4 max-h-[460px] overflow-y-auto space-y-0.5">
                  {unifiedLines.map((line, idx) => {
                    const isAdded = line.type === 'added';
                    const isRemoved = line.type === 'removed';
                    return (
                      <div
                        key={idx}
                        className={`flex items-start px-2 py-0.5 rounded leading-relaxed transition-colors ${
                          isAdded
                            ? 'bg-emerald-950/70 text-emerald-300 font-semibold'
                            : isRemoved
                            ? 'bg-rose-950/70 text-rose-300 font-semibold'
                            : 'text-slate-300 hover:bg-slate-900/60'
                        }`}
                      >
                        <span className="w-8 shrink-0 select-none text-slate-600 text-right pr-3 font-mono">
                          {line.lineNumber}
                        </span>
                        <span
                          className={`w-4 shrink-0 select-none font-bold ${
                            isAdded ? 'text-emerald-400' : isRemoved ? 'text-rose-400' : 'text-slate-600'
                          }`}
                        >
                          {line.prefix}
                        </span>
                        <pre className="flex-1 font-mono whitespace-pre-wrap break-all">
                          {line.content}
                        </pre>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Description & Audit metadata */}
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-xs text-slate-600 space-y-1">
            <div>
              <strong>版本修订说明：</strong> {targetPolicy.description || '未记录版本修订说明。'}
            </div>
            <div>
              <strong>修订人：</strong> {targetPolicy.created_by} • <strong>创建时间：</strong>{' '}
              {formatDateTimeZh(targetPolicy.created_at)}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-100 transition-colors cursor-pointer"
          >
            关闭对比
          </button>

          {!isCurrentActive && onActivate && (
            <button
              type="button"
              onClick={onActivate}
              disabled={isActivating}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition-colors flex items-center gap-2 cursor-pointer"
            >
              {isActivating ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              应用并切换为当前版本 (v{targetPolicy.version})
            </button>
          )}

          {isCurrentActive && (
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-200 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" /> 当前正在生效的策略版本
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
