import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sliders,
  Plus,
  History,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  GitCompare,
} from 'lucide-react';
import {
  getDispatchPolicies,
  createDispatchPolicy,
  activateDispatchPolicy,
} from '../../api/adminApi';
import { DispatchPolicy, DispatchPolicyCreateInput, DispatchWeights } from '../../types/admin';
import { PolicyDiffModal } from '../../components/admin/PolicyDiffModal';
import { formatDateTimeZh } from '../../utils/dateTime';

export const AdminDispatchPolicyPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [weightsForm, setWeightsForm] = useState<DispatchWeights>({
    workload_weight: 25,
    capacity_weight: 20,
    sla_weight: 30,
    travel_weight: 15,
    overtime_penalty: 10,
  });
  const [description, setDescription] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [diffTarget, setDiffTarget] = useState<DispatchPolicy | null>(null);

  const { data: policies, isLoading } = useQuery({
    queryKey: ['admin-dispatch-policies'],
    queryFn: getDispatchPolicies,
  });

  const activePolicy = Array.isArray(policies) ? policies.find((p) => p.is_active) : undefined;

  const totalSum =
    weightsForm.workload_weight +
    weightsForm.capacity_weight +
    weightsForm.sla_weight +
    weightsForm.travel_weight +
    weightsForm.overtime_penalty;

  const createMutation = useMutation({
    mutationFn: createDispatchPolicy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-dispatch-policies'] });
      setIsCreateOpen(false);
      setDescription('');
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '创建派单策略新版本失败。');
    },
  });

  const activateMutation = useMutation({
    mutationFn: (version: number) => activateDispatchPolicy(version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-dispatch-policies'] });
      setDiffTarget(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '激活策略版本失败。');
    },
  });

  const getWeightFactorZh = (factor: string) => {
    switch (factor) {
      case 'workload_weight':
        return '当前负载权重';
      case 'capacity_weight':
        return '服务网格容量';
      case 'sla_weight':
        return '服务时效权重';
      case 'travel_weight':
        return '路程成本权重';
      case 'overtime_penalty':
        return '超时惩罚因子';
      default:
        return factor;
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">派单策略版本管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            微调智能派单多因子评分权重。所有策略版本均经审计记录，支持平滑切换与一键版本回滚。
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          发布策略新版本
        </button>
      </div>

      {/* Error Alert */}
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
            关闭提示
          </button>
        </div>
      )}

      {/* Active Policy Highlight Card */}
      {activePolicy && (
        <div className="bg-white rounded-2xl border border-indigo-100 shadow-sm p-6 bg-gradient-to-br from-white to-indigo-50/30 space-y-5">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-indigo-100/60">
            <div className="flex items-center space-x-3">
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-600 text-white shadow-xs">
                版本 v{activePolicy.version} (当前正在生效)
              </span>
              <span className="text-xs text-slate-500">
                修订人：<strong>{activePolicy.created_by}</strong> • 创建时间：{' '}
                {formatDateTimeZh(activePolicy.created_at)}
              </span>
            </div>
            {activePolicy.description && (
              <span className="text-xs text-slate-600 italic bg-white px-3 py-1 rounded-lg border border-slate-200/60">
                &ldquo;{activePolicy.description}&rdquo;
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-5 gap-4">
            {Object.entries(activePolicy.weights).map(([factor, weight]) => (
              <div key={factor} className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                  {getWeightFactorZh(factor)}
                </span>
                <span className="text-2xl font-bold text-slate-900 mt-1 block font-mono">{weight}%</span>
                <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-full rounded-full"
                    style={{ width: `${Math.min(weight, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Version History Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-slate-500" />
            <h3 className="font-bold text-slate-900 text-sm">策略历史版本履历</h3>
          </div>
          <span className="text-xs text-slate-400">累计策略版本：{policies?.length ?? 0} 个</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">版本</th>
                <th className="px-6 py-3.5">权重因子分布</th>
                <th className="px-6 py-3.5">修订人</th>
                <th className="px-6 py-3.5">创建时间</th>
                <th className="px-6 py-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                    正在加载策略历史记录…
                  </td>
                </tr>
              ) : Array.isArray(policies) && policies.length > 0 ? (
                policies.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 font-mono">v{p.version}</span>
                        {p.is_active && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            当前生效
                          </span>
                        )}
                      </div>
                      {p.description && (
                        <div className="text-xs text-slate-500 mt-0.5">{p.description}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-700">
                      负载:{p.weights.workload_weight}% • 容量:{p.weights.capacity_weight}% • 时效:
                      {p.weights.sla_weight}% • 路程:{p.weights.travel_weight}% • 惩罚:
                      {p.weights.overtime_penalty}%
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-600">{p.created_by}</td>
                    <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                      {formatDateTimeZh(p.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => setDiffTarget(p)}
                        className="px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors inline-flex items-center gap-1 cursor-pointer"
                      >
                        <GitCompare className="w-3.5 h-3.5" />
                        版本对比
                      </button>

                      {!p.is_active && (
                        <button
                          onClick={() => activateMutation.mutate(p.version)}
                          disabled={activateMutation.isPending}
                          className="px-2.5 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 rounded-lg transition-colors inline-flex items-center gap-1 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3" />
                          一键回滚
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                    暂无派单策略记录。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Version Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">发布策略新版本</h3>
            <p className="text-xs text-slate-500 mb-4">
              各项权重因子累计之和必须精确为 100%。新版本发布后将即刻成为线上决策基准。
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (totalSum !== 100) {
                  setErrorMessage(`权重总和必须等于 100%（当前为 ${totalSum}%）。`);
                  return;
                }
                createMutation.mutate({
                  weights: weightsForm,
                  description: description || undefined,
                  set_active: true,
                });
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  版本修订说明
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="例如：夏季空调高峰期提升服务时效权重"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="space-y-3 bg-slate-50 p-4 rounded-lg border border-slate-200">
                {(Object.keys(weightsForm) as (keyof DispatchWeights)[]).map((key) => (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <span className="text-xs font-medium text-slate-700 flex-1">
                      {getWeightFactorZh(key)}
                    </span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={weightsForm[key]}
                      onChange={(e) =>
                        setWeightsForm({
                          ...weightsForm,
                          [key]: parseInt(e.target.value, 10) || 0,
                        })
                      }
                      className="w-20 px-2 py-1 text-right text-xs font-mono border border-slate-300 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <span className="text-xs text-slate-400 w-4">%</span>
                  </div>
                ))}

                <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-xs font-bold">
                  <span>权重之和校验：</span>
                  <span className={totalSum === 100 ? 'text-emerald-600 font-mono' : 'text-rose-600 font-mono'}>
                    {totalSum}% {totalSum === 100 ? '✓ (有效合规)' : '(必须等于 100%)'}
                  </span>
                </div>
              </div>

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
                  disabled={createMutation.isPending || totalSum !== 100}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {createMutation.isPending ? '正在发布…' : '确认发布并生效'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Policy Diff Modal */}
      {diffTarget && (
        <PolicyDiffModal
          isOpen={true}
          type="dispatch"
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
