import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Wrench,
  Plus,
  Edit2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Flame,
  Clock,
  Briefcase,
  Building2,
  Users,
} from 'lucide-react';
import {
  getAdminTechnicians,
  createTechnician,
  updateTechnician,
  activateTechnician,
  deactivateTechnician,
} from '../../api/adminApi';
import { TechnicianAdmin, TechnicianCreateInput, TechnicianUpdateInput } from '../../types/admin';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { branches, teams, ServiceBranch, ServiceTeam, getServiceTypeText } from '../../locales';

export const AdminTechniciansPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingTech, setEditingTech] = useState<TechnicianAdmin | null>(null);

  const [createForm, setCreateForm] = useState<TechnicianCreateInput>({
    name: '',
    service_area: '广州天河服务中心',
    skills: ['HVAC'],
    max_daily_work_minutes: 480,
    max_daily_jobs: 5,
    is_available_for_emergency: false,
  });

  const [editForm, setEditForm] = useState<TechnicianUpdateInput>({});

  const [deactivateTarget, setDeactivateTarget] = useState<TechnicianAdmin | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: technicians, isLoading } = useQuery({
    queryKey: ['admin-technicians'],
    queryFn: getAdminTechnicians,
  });

  const createMutation = useMutation({
    mutationFn: createTechnician,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-technicians'] });
      setIsCreateOpen(false);
      setCreateForm({
        name: '',
        service_area: '广州天河服务中心',
        skills: ['HVAC'],
        max_daily_work_minutes: 480,
        max_daily_jobs: 5,
        is_available_for_emergency: false,
      });
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '新建工程师失败，请检查填写参数。');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: TechnicianUpdateInput }) =>
      updateTechnician(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-technicians'] });
      setEditingTech(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '更新工程师参数失败。');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => deactivateTechnician(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-technicians'] });
      setDeactivateTarget(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '停用失败：该工程师有正在进行或未来待履约的上门任务，存在调度冲突 (409)。');
      setDeactivateTarget(null);
    },
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => activateTechnician(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-technicians'] });
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '启用工程师失败。');
    },
  });

  // Helper to map branch & team from area
  const getBranchAndTeam = (tech: TechnicianAdmin) => {
    const matchedTeam = teams.find((tm: ServiceTeam) => tm.memberTechnicianIds.includes(tech.id)) || teams[tech.id % teams.length];
    const matchedBranch = branches.find((b: ServiceBranch) => b.id === matchedTeam?.branchId) || branches[0];
    return {
      branchName: matchedBranch.name,
      teamName: matchedTeam.name,
    };
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">服务工程师管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            配置全域工程师网点归属、服务班组、技能资质、每日负荷上限及紧急值班状态。
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          新增服务工程师
        </button>
      </div>

      {/* Global Error Alert (e.g., 409 Conflict) */}
      {errorMessage && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0" />
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

      {/* Technicians Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3.5">工程师姓名 / 工号</th>
                <th className="px-5 py-3.5">所属网点 / 班组</th>
                <th className="px-5 py-3.5">专业技能</th>
                <th className="px-5 py-3.5">值班状态</th>
                <th className="px-5 py-3.5">每日负载限额</th>
                <th className="px-5 py-3.5">启用状态</th>
                <th className="px-5 py-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-400 text-xs">
                    正在加载工程师数据…
                  </td>
                </tr>
              ) : Array.isArray(technicians) && technicians.length > 0 ? (
                technicians.map((t) => {
                  const { branchName, teamName } = getBranchAndTeam(t);
                  return (
                    <tr key={t.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-slate-900">{t.name}</div>
                        <div className="text-xs text-slate-400 font-mono">工号：#{t.id}</div>
                      </td>
                      <td className="px-5 py-4 text-xs">
                        <div className="font-medium text-slate-800 flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          <span>{branchName}</span>
                        </div>
                        <div className="text-slate-500 text-[11px] flex items-center gap-1 mt-0.5">
                          <Users className="w-3 h-3 text-slate-400" />
                          <span>{teamName}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {Array.isArray(t.skills) && t.skills.map((skill) => (
                            <span
                              key={skill}
                              className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700"
                            >
                              {getServiceTypeText(skill)}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        {t.is_available_for_emergency ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            <Flame className="w-3 h-3 text-rose-600" />
                            紧急值班中
                          </span>
                        ) : (
                          <span className="text-xs text-slate-500 font-medium">常规在岗</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-600">
                        <div className="flex items-center gap-1.5 font-mono">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>{t.max_daily_work_minutes} 分钟/天</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5 text-slate-500 font-mono">
                          <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                          <span>上限 {t.max_daily_jobs} 单/天</span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        {t.status === 'active' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            正常在册
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                            <XCircle className="w-3.5 h-3.5 text-slate-400" />
                            已停用
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-right space-x-2">
                        <button
                          onClick={() => {
                            setEditingTech(t);
                            setEditForm({
                              max_daily_work_minutes: t.max_daily_work_minutes,
                              max_daily_jobs: t.max_daily_jobs,
                              is_available_for_emergency: t.is_available_for_emergency,
                            });
                          }}
                          className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                          title="修改产能限额"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>

                        {t.status === 'active' ? (
                          <button
                            onClick={() => setDeactivateTarget(t)}
                            className="px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 transition-colors cursor-pointer"
                          >
                            停用
                          </button>
                        ) : (
                          <button
                            onClick={() => activateMutation.mutate(t.id)}
                            className="px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors cursor-pointer"
                          >
                            启用
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-400 text-xs">
                    暂无在册的服务工程师。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Technician Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">新增服务工程师</h3>
            <p className="text-xs text-slate-500 mb-4">
              登记工程师基本档案、服务网点所属以及每日派单限额指标。
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate(createForm);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">工程师姓名</label>
                <input
                  type="text"
                  required
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  placeholder="例如：陈志强"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">服务网点 / 区域</label>
                <select
                  value={createForm.service_area}
                  onChange={(e) => setCreateForm({ ...createForm, service_area: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer"
                >
                  {branches.map((b: ServiceBranch) => (
                    <option key={b.id} value={b.name}>{b.name} ({b.code})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  专业技能 (英文或中文，逗号分隔)
                </label>
                <input
                  type="text"
                  value={createForm.skills.join(', ')}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      skills: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="HVAC, Plumbing, Electrical"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    每日作业上限 (分钟)
                  </label>
                  <input
                    type="number"
                    min={60}
                    max={1440}
                    value={createForm.max_daily_work_minutes}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, max_daily_work_minutes: parseInt(e.target.value, 10) })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">每日工单上限 (单)</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={createForm.max_daily_jobs}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, max_daily_jobs: parseInt(e.target.value, 10) })
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="emergency"
                  checked={createForm.is_available_for_emergency}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, is_available_for_emergency: e.target.checked })
                  }
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
                />
                <label htmlFor="emergency" className="text-xs font-medium text-slate-700 cursor-pointer">
                  支持紧急工单 (P0/P1) 紧急呼叫派工
                </label>
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
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors flex items-center gap-2 cursor-pointer"
                >
                  {createMutation.isPending ? '正在登记…' : '确认登记'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Capacity Modal */}
      {editingTech && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">
              调整产能参数：{editingTech.name}
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              更新服务工程师的每日作业负荷阈值与紧急排班属性。
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                updateMutation.mutate({ id: editingTech.id, data: editForm });
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  每日作业时长上限 (分钟)
                </label>
                <input
                  type="number"
                  min={60}
                  max={1440}
                  value={editForm.max_daily_work_minutes ?? 480}
                  onChange={(e) =>
                    setEditForm({ ...editForm, max_daily_work_minutes: parseInt(e.target.value, 10) })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">每日工单上限 (单)</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={editForm.max_daily_jobs ?? 5}
                  onChange={(e) =>
                    setEditForm({ ...editForm, max_daily_jobs: parseInt(e.target.value, 10) })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="edit_emergency"
                  checked={editForm.is_available_for_emergency ?? false}
                  onChange={(e) =>
                    setEditForm({ ...editForm, is_available_for_emergency: e.target.checked })
                  }
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
                />
                <label htmlFor="edit_emergency" className="text-xs font-medium text-slate-700 cursor-pointer">
                  支持紧急工单 (P0/P1) 呼叫派单
                </label>
              </div>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setEditingTech(null)}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  {updateMutation.isPending ? '正在保存…' : '保存产能配置'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Conflict Check Deactivate Dialog */}
      {deactivateTarget && (
        <ConfirmDialog
          isOpen={true}
          title={`确认停用服务工程师：${deactivateTarget.name}？`}
          message={`停用工程师后，系统派单推荐引擎将不再为其分配新的服务工单。提示：若该工程师名下有尚未完工的未来预约任务，系统将返回 409 Conflict 冲突并拒绝停用。`}
          confirmLabel="确认停用工程师"
          confirmVariant="danger"
          isLoading={deactivateMutation.isPending}
          onConfirm={() => deactivateMutation.mutate(deactivateTarget.id)}
          onCancel={() => setDeactivateTarget(null)}
        />
      )}
    </div>
  );
};
