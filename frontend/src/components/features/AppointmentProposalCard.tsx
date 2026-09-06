import React, { useState } from 'react';
import { AppointmentProposal } from '../../types/api';
import { useAuth } from '../../auth/useAuth';
import { formatTimeRangeZh } from '../../utils/dateTime';
import { Check, X, Calendar, MapPin, Wrench, AlertTriangle, ShieldCheck, RefreshCw, Loader2 } from 'lucide-react';
import { getServiceTypeText } from '../../locales';

interface AppointmentProposalCardProps {
  proposal: AppointmentProposal;
  isSubmitting?: boolean;
  errorMessage?: string | null;
  onApprove: (note?: string) => Promise<void>;
  onReject: (reason?: string) => Promise<void>;
}

export const AppointmentProposalCard: React.FC<AppointmentProposalCardProps> = ({
  proposal,
  isSubmitting = false,
  errorMessage = null,
  onApprove,
  onReject,
}) => {
  const { canAct, isViewer } = useAuth();
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [approvalNote, setApprovalNote] = useState('');

  const handleApprove = async () => {
    if (isSubmitting) return;
    await onApprove(approvalNote);
  };

  const handleReject = async () => {
    if (isSubmitting) return;
    await onReject(rejectReason);
    setShowRejectForm(false);
  };

  return (
    <div className="rounded-2xl border border-indigo-200 bg-white shadow-card overflow-hidden">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 px-6 py-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Calendar className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold tracking-tight">推荐上门预约方案 (待调度员确认)</h3>
          </div>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-amber-400 text-amber-950 shadow-xs">
            人工决策审核 (HITL)
          </span>
        </div>
        <p className="text-xs text-indigo-200 mt-1 leading-relaxed">
          智能派单引擎已根据技能匹配、就近网格、工单负荷与服务时效生成推荐上门方案。
        </p>
      </div>

      <div className="p-6 space-y-5">
        {/* Error / Conflict Alert Banner */}
        {errorMessage && (
          <div
            role="alert"
            className="rounded-xl bg-rose-50 border border-rose-300 p-4 text-xs text-rose-900 flex items-start gap-3 shadow-xs"
          >
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-bold text-sm text-rose-900">
                调度冲突 / 操作失败
              </div>
              <p className="mt-1 leading-relaxed">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Proposal Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50/70 p-5 rounded-xl border border-slate-200 text-xs">
          <div>
            <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider block mb-1">
              推荐服务工程师
            </span>
            <div className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              {proposal.technician_name}
            </div>
          </div>

          <div>
            <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider block mb-1">
              建议上门时间窗口 (中国标准时间)
            </span>
            <div className="font-semibold text-slate-900 font-mono text-sm">
              {formatTimeRangeZh(proposal.start_time, proposal.end_time)}
            </div>
          </div>

          <div>
            <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider block mb-1">
              报修类别
            </span>
            <div className="font-medium text-slate-800 flex items-center gap-1.5">
              <Wrench className="w-3.5 h-3.5 text-slate-400" />
              {getServiceTypeText(proposal.service_type)}
            </div>
          </div>

          <div>
            <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider block mb-1">
              服务网格 / 地址
            </span>
            <div className="font-medium text-slate-800 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {proposal.location || '待确认位置'}
            </div>
          </div>

          <div className="md:col-span-2 pt-2 border-t border-slate-200/80">
            <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider block mb-1">
              推荐理由与综合决策依据
            </span>
            <div className="text-slate-700 italic flex items-start gap-1.5 leading-relaxed">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0 mt-0.5" />
              <span>{proposal.dispatch_reason}</span>
            </div>
          </div>
        </div>

        {/* Optional Operator Approval Note */}
        {!showRejectForm && canAct && (
          <div>
            <label
              htmlFor="approval-note"
              className="block text-xs font-semibold text-slate-700 mb-1"
            >
              调度派工备注 / 现场协同指令 (选填)
            </label>
            <input
              id="approval-note"
              type="text"
              value={approvalNote}
              onChange={(e) => setApprovalNote(e.target.value)}
              placeholder="例如：门禁密码 1234，到场前请提前 30 分钟电话联系客户"
              disabled={isSubmitting}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
        )}

        {/* Rejection Form Section */}
        {showRejectForm && (
          <div className="p-4 bg-rose-50/70 rounded-xl border border-rose-200 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-rose-900">
                协商改派 / 重新调度
              </h4>
              <button
                type="button"
                onClick={() => setShowRejectForm(false)}
                className="text-slate-400 hover:text-slate-600 text-xs cursor-pointer"
              >
                取消
              </button>
            </div>
            <p className="text-xs text-rose-700">
              请填写改派或驳回说明，该工单将重新触发派工匹配或进入改期协商流程。
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="例如：客户要求更换指定技能工程师、时隙冲突需重新协调…"
              rows={2}
              className="w-full text-xs rounded-lg border border-rose-300 p-2.5 focus:ring-2 focus:ring-rose-500 focus:outline-none bg-white"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowRejectForm(false)}
                disabled={isSubmitting}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={isSubmitting}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs cursor-pointer"
              >
                确认改派并重新进入调度
              </button>
            </div>
          </div>
        )}

        {/* Viewer Role Notification */}
        {isViewer && (
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500">
            只读角色：仅具备查看权限，无法确认或改派方案。
          </div>
        )}

        {/* Action Controls for Operator/Admin */}
        {!showRejectForm && canAct && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <div className="text-xs text-slate-500">
              确认后将锁定工程师日程并同步至 Google Calendar 日历。
            </div>

            <div className="flex items-center space-x-3 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => setShowRejectForm(true)}
                disabled={isSubmitting}
                className="inline-flex items-center justify-center font-medium rounded-lg text-xs px-3 py-2 gap-1.5 border border-rose-200 text-rose-700 bg-white hover:bg-rose-50 disabled:opacity-50 transition-colors cursor-pointer"
              >
                <X className="w-3.5 h-3.5 text-rose-600" />
                协商改派 / 重新调度
              </button>

              <button
                type="button"
                onClick={handleApprove}
                disabled={isSubmitting}
                className="inline-flex items-center justify-center font-medium rounded-lg text-xs px-4 py-2 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs disabled:opacity-50 transition-colors cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    正在锁定派工…
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    确认派单并预约
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
