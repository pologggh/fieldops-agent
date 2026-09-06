import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users,
  UserPlus,
  Shield,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  KeyRound,
} from 'lucide-react';
import {
  getInternalUsers,
  createInternalUser,
  activateInternalUser,
  deactivateInternalUser,
  changeUserRole,
} from '../../api/adminApi';
import { InternalUser, InternalUserCreateInput } from '../../types/admin';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { formatDateTimeZh } from '../../utils/dateTime';

export const AdminUsersPage: React.FC = () => {
  const queryClient = useQueryClient();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<InternalUserCreateInput>({
    email: '',
    name: '',
    role: 'operator',
    password: '',
  });

  const [confirmTarget, setConfirmTarget] = useState<{
    user: InternalUser;
    action: 'activate' | 'deactivate';
  } | null>(null);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: getInternalUsers,
  });

  const createMutation = useMutation({
    mutationFn: createInternalUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setIsCreateOpen(false);
      setCreateForm({ email: '', name: '', role: 'operator', password: '' });
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '创建用户失败，请检查填写信息。');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: number) => deactivateInternalUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setConfirmTarget(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '停用用户失败（末位管理员自保护拦截）。');
      setConfirmTarget(null);
    },
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => activateInternalUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setConfirmTarget(null);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '启用用户失败。');
      setConfirmTarget(null);
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) => changeUserRole(id, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || '更新用户角色失败。');
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">平台用户管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            配置内部账号、分配基于角色的访问权限 (RBAC) 以及维护账号启用/停用状态。
          </p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <UserPlus className="w-4 h-4" />
          新建内部用户
        </button>
      </div>

      {/* Global Error Banner */}
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

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">用户姓名 / 账号</th>
                <th className="px-6 py-3.5">系统角色</th>
                <th className="px-6 py-3.5">账号状态</th>
                <th className="px-6 py-3.5">最近登录时间</th>
                <th className="px-6 py-3.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                    正在加载用户数据…
                  </td>
                </tr>
              ) : Array.isArray(users) && users.length > 0 ? (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{u.name}</div>
                      <div className="text-xs text-slate-400 font-mono">{u.email}</div>
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={u.role}
                        onChange={(e) => roleMutation.mutate({ id: u.id, role: e.target.value })}
                        disabled={roleMutation.isPending}
                        className="text-xs font-semibold bg-slate-100 border border-slate-300 rounded px-2.5 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-rose-500 cursor-pointer"
                      >
                        <option value="admin">管理员 (admin)</option>
                        <option value="operator">调度员 (operator)</option>
                        <option value="viewer">只读观察员 (viewer)</option>
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          已启用
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          <XCircle className="w-3.5 h-3.5 text-slate-400" />
                          已停用
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">
                      {u.last_login ? (
                        <span className="flex items-center gap-1 font-mono">
                          <Clock className="w-3 h-3 text-slate-400" />
                          {formatDateTimeZh(u.last_login)}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">尚未登录</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {u.is_active ? (
                        <button
                          onClick={() => setConfirmTarget({ user: u, action: 'deactivate' })}
                          className="px-3 py-1.5 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-lg hover:bg-rose-100 transition-colors cursor-pointer"
                        >
                          停用账号
                        </button>
                      ) : (
                        <button
                          onClick={() => setConfirmTarget({ user: u, action: 'activate' })}
                          className="px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors cursor-pointer"
                        >
                          重新启用
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-slate-400 text-xs">
                    暂无注册的内部用户账号。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1">新建内部平台用户</h3>
            <p className="text-xs text-slate-500 mb-4">
              创建用于调度控制中心或系统治理的账号，并指定初始权限。
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate(createForm);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">用户姓名</label>
                <input
                  type="text"
                  required
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  placeholder="例如：陈调度员"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">电子邮箱 (登录账号)</label>
                <input
                  type="email"
                  required
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  placeholder="user@fieldops.com"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">系统角色</label>
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, role: e.target.value as 'admin' | 'operator' | 'viewer' })
                  }
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500 cursor-pointer"
                >
                  <option value="operator">调度员 (可审单、派单、改派、完工)</option>
                  <option value="viewer">只读观察员 (仅可查看，无写操作权限)</option>
                  <option value="admin">系统管理员 (策略配置、用户管理、系统治理)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">初始密码</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  placeholder="至少 6 个字符"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
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
                  className="px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition-colors flex items-center gap-2 cursor-pointer"
                >
                  {createMutation.isPending ? '正在创建…' : '创建用户'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog for Soft-Disable / Activation */}
      {confirmTarget && (
        <ConfirmDialog
          isOpen={true}
          title={
            confirmTarget.action === 'deactivate'
              ? `确认停用账号：${confirmTarget.user.name}？`
              : `确认重新启用：${confirmTarget.user.name}？`
          }
          message={
            confirmTarget.action === 'deactivate'
              ? `停用后该用户将立即无法登录系统，且所有 API 凭据将失效。若该账号为系统最后一名活跃管理员，系统将触发自保护防御机制并拒绝停用。`
              : `启用后该用户将恢复登录权限及相应角色权限。`
          }
          confirmLabel={confirmTarget.action === 'deactivate' ? '确认停用账号' : '确认重新启用'}
          confirmVariant={confirmTarget.action === 'deactivate' ? 'danger' : 'primary'}
          isLoading={deactivateMutation.isPending || activateMutation.isPending}
          onConfirm={() => {
            if (confirmTarget.action === 'deactivate') {
              deactivateMutation.mutate(confirmTarget.user.id);
            } else {
              activateMutation.mutate(confirmTarget.user.id);
            }
          }}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
};
