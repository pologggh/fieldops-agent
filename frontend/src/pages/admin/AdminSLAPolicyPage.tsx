import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Timer,
  Plus,
  History,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  GitCompare,
  ShieldCheck,
} from 'lucide-react';
import {
  getSLAPolicies,
  createSLAPolicy,
  activateSLAPolicy,
} from '../../api/adminApi';
import { SLAPolicy, SLATargetTier } from '../../types/admin';
import { PolicyDiffModal } from '../../components/admin/PolicyDiffModal';
import { formatDateTimeZh } from '../../utils/dateTime';

const TIER_NAMES: Record<string, { label: string; badge: string; color: string }> = {
  P0: { label: 'P0 紧急保障', badge: '最急响应', color: 'bg-rose-50 text-rose-700 border-rose-200' },
  P1: { label: 'P1 高优工单', badge: '快速跟进', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  P2: { label: 'P2 普通服务', badge: '标准时限', color: 'bg-blue-50 text-blue-700 border-blue-200' },
  P3: { label: 'P3 常规保养', badge: '常态维护', color: 'bg-slate-100 text-slate-700 border-slate-200' },
};

export const AdminSLAPolicyPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [description, setDescription] = useState('');
  const [targetsForm, setTargetsForm] = useState<Record<string, SLATargetTier>>({
    P0: { response_minutes: 15, assignment_minutes: 30, service_start_minutes: 120, at_risk_threshold_minutes: 15 },
    P1: { response_minutes: 30, assignment_minutes: 60, service_start_minutes: 240, at_risk_threshold_minutes: 30 },
    P2: { response_minutes: 60, assignment_minutes: 120, service_start_minutes: 480, at_risk_threshold_minutes: 60 },
    P3: { response_minutes: 120, assignment_minutes: 240, service_start_minutes: 1440, at_risk_threshold_minutes: 120 },
  });

  const [diffTarget, setDiffTarget] = useState<SLAPolicy | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: policies, isLoading } = useQuery({
    queryKey: ['admin-sla-policies'],
    queryFn: getSLAPolicies,
  });

  const activePolicy = Array.isArray(policies) ? policies.find((p) => p.is_active) : undefined;

  const createMutation = useMutation({
    mutationFn: createSLAPolicy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-sla-policies'] });
      setIsCreateOpen(false);
      setDescription('');
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '创建并发布新 SLA 策略失败。');
    },
  });

  const activateMutation = useMutation({
    mutationFn: (version: number) => activateSLAPolicy(version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-sla-policies'] });
      setDiffTarget(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '启用该 SLA 策略版本失败。');
    },
  });

  return (
    <div className="space-y-8">
      {/* 头部标题与操作 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">服务时效指标与升级策略 (SLA)</h1>
          <p className="text-sm text-slate-500 mt-1">
            按紧急程度梯度设定初次响应、派单锁定及工程师到场服务时限与临期预警阈值。
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          发布新策略版本
        </button>
      </div>

      {/* 历史不可篡改准则横幅 */}
      <div className="p-4 rounded-xl bg-indigo-50/60 border border-indigo-200/70 text-indigo-900 text-xs flex items-center gap-3">
        <ShieldCheck className="w-5 h-5 text-indigo-600 flex-shrink-0" />
        <div>
          <strong>历史时效不可篡改准则：</strong> 启用新的 SLA 策略版本仅对后续产生的新工单生效。已创建的历史工单与已办结记录严格保留其创建时的 SLA 考核基准与超时时间点，不发生追溯修改。
        </div>
      </div>

      {/* 错误提示 */}
      {errorMessage && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-rose-600 font-semibold hover:underline cursor-pointer"
          >
            忽略
          </button>
        </div>
      )}

      {/* 当前运行中的 SLA 矩阵卡片 */}
      {activePolicy && (
        <div className="bg-white rounded-xl border border-amber-200 shadow-sm p-6 bg-gradient-to-br from-white to-amber-50/20">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-amber-100">
            <div className="flex items-center space-x-3">
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-600 text-white shadow-xs">
                SLA 策略版本 v{activePolicy.version}（当前生效）
              </span>
              <span className="text-xs text-slate-500">
                由 <strong>{activePolicy.created_by}</strong> 于{' '}
                {formatDateTimeZh(activePolicy.created_at)} 发布
              </span>
            </div>
            {activePolicy.description && (
              <span className="text-xs text-slate-600 bg-white px-3 py-1 rounded-lg border border-slate-200/60">
                &ldquo;{activePolicy.description}&rdquo;
              </span>
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(activePolicy.targets).map(([tier, targets]) => {
              const meta = TIER_NAMES[tier] || { label: `${tier} 级工单`, badge: '指标限额', color: 'bg-slate-50 text-slate-700 border-slate-200' };
              return (
                <div key={tier} className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <span className="text-sm font-bold text-slate-900">{meta.label}</span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${meta.color}`}>
                      {meta.badge}
                    </span>
                  </div>

                  <div className="mt-3 space-y-2 text-xs">
                    <div className="flex justify-between text-slate-600">
                      <span>初次响应限时：</span>
                      <strong className="text-slate-900 font-mono">{targets.response_minutes} 分钟</strong>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>派单锁定限时：</span>
                      <strong className="text-slate-900 font-mono">{targets.assignment_minutes} 分钟</strong>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>到场服务限时：</span>
                      <strong className="text-slate-900 font-mono">{targets.service_start_minutes} 分钟</strong>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>临期预警缓冲：</span>
                      <strong className="text-amber-700 font-mono">提前 {targets.at_risk_threshold_minutes} 分钟</strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 版本历史归档 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-slate-500" />
            <h3 className="font-bold text-slate-900 text-sm">SLA 策略版本历史归档</h3>
          </div>
          <span className="text-xs text-slate-400">总计版本数：{policies?.length ?? 0}</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">策略版本</th>
                <th className="px-6 py-3.5">核心考核时限 (P0 / P1)</th>
                <th className="px-6 py-3.5">发布操作人</th>
                <th className="px-6 py-3.5">发布时间</th>
                <th className="px-6 py-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    正在载入 SLA 策略版本记录...
                  </td>
                </tr>
              ) : Array.isArray(policies) && policies.length > 0 ? (
                policies.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900">v{p.version}</span>
                        {p.is_active && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            运行中
                          </span>
                        )}
                      </div>
                      {p.description && (
                        <div className="text-xs text-slate-500 mt-0.5">{p.description}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-600">
                      P0: 响应 {p.targets?.P0?.response_minutes}m · 派单 {p.targets?.P0?.assignment_minutes}m · 到场 {p.targets?.P0?.service_start_minutes}m
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-600">{p.created_by}</td>
                    <td className="px-6 py-4 text-xs text-slate-400">
                      {formatDateTimeZh(p.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => setDiffTarget(p)}
                        className="px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors inline-flex items-center gap-1 cursor-pointer"
                      >
                        <GitCompare className="w-3.5 h-3.5" />
                        比对差异
                      </button>

                      {!p.is_active && (
                        <button
                          onClick={() => activateMutation.mutate(p.version)}
                          disabled={activateMutation.isPending}
                          className="px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 rounded-lg transition-colors inline-flex items-center gap-1 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          回滚至此版本
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                    暂无 SLA 策略归档记录。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 创建版本弹窗 */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-xl w-full p-6 border border-slate-200 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-slate-900 mb-1">发布新 SLA 策略版本</h3>
            <p className="text-xs text-slate-500 mb-4">
              请为各优先级工单设定响应、派单锁定及到场服务的目标时限（单位：分钟）。
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate({
                  targets: targetsForm,
                  description: description || undefined,
                  set_active: true,
                });
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  版本更新说明
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="例如：收紧夏季空调高峰期 P0 应急派单与到场时效"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              {['P0', 'P1', 'P2', 'P3'].map((tier) => {
                const meta = TIER_NAMES[tier];
                return (
                  <div key={tier} className="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-3">
                    <h4 className="font-bold text-xs text-slate-800 tracking-wider">
                      {meta?.label || tier} 指标阈值（分钟）
                    </h4>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-500">初次响应限时</label>
                        <input
                          type="number"
                          min={1}
                          value={targetsForm[tier].response_minutes}
                          onChange={(e) =>
                            setTargetsForm({
                              ...targetsForm,
                              [tier]: {
                                ...targetsForm[tier],
                                response_minutes: parseInt(e.target.value, 10) || 1,
                              },
                            })
                          }
                          className="w-full px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500">派单锁定限时</label>
                        <input
                          type="number"
                          min={1}
                          value={targetsForm[tier].assignment_minutes}
                          onChange={(e) =>
                            setTargetsForm({
                              ...targetsForm,
                              [tier]: {
                                ...targetsForm[tier],
                                assignment_minutes: parseInt(e.target.value, 10) || 1,
                              },
                            })
                          }
                          className="w-full px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500">到场服务限时</label>
                        <input
                          type="number"
                          min={1}
                          value={targetsForm[tier].service_start_minutes}
                          onChange={(e) =>
                            setTargetsForm({
                              ...targetsForm,
                              [tier]: {
                                ...targetsForm[tier],
                                service_start_minutes: parseInt(e.target.value, 10) || 1,
                              },
                            })
                          }
                          className="w-full px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500">临期预警提前</label>
                        <input
                          type="number"
                          min={1}
                          value={targetsForm[tier].at_risk_threshold_minutes}
                          onChange={(e) =>
                            setTargetsForm({
                              ...targetsForm,
                              [tier]: {
                                ...targetsForm[tier],
                                at_risk_threshold_minutes: parseInt(e.target.value, 10) || 1,
                              },
                            })
                          }
                          className="w-full px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                        />
                      </div>
                    </div>
                  </div>
                );
              })}

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  {createMutation.isPending ? '正在发布...' : '确认发布新策略版本'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 策略版本比对弹窗 */}
      {diffTarget && (
        <PolicyDiffModal
          isOpen={true}
          type="sla"
          activePolicy={activePolicy ?? null}
          targetPolicy={diffTarget}
          onClose={() => setDiffTarget(null)}
          onActivate={() => activateMutation.mutate(diffTarget.version)}
          isActivating={activateMutation.isPending}
        />
      )}
    </div>
  );
};
