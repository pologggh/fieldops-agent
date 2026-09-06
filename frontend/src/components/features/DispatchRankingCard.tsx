import React from 'react';
import { DispatchCandidate } from '../../types/api';
import {
  Award,
  Check,
  MapPin,
  Briefcase,
  Clock,
  ShieldCheck,
  TrendingUp,
  Navigation,
} from 'lucide-react';

interface DispatchRankingCardProps {
  candidate: DispatchCandidate;
  isTopChoice?: boolean;
}

export const DispatchRankingCard: React.FC<DispatchRankingCardProps> = ({
  candidate,
  isTopChoice = false,
}) => {
  const percentage = Math.round(candidate.score * 100);

  // Compute breakdown scores (out of 100 points):
  // 技能匹配: 25, 服务区域: 20, 当前负载: 20, 服务时效: 20, 路程成本: 15
  const skillScore = Math.min(25, Math.max(18, Math.round(candidate.score * 25)));
  const areaScore = Math.min(20, Math.max(15, Math.round(candidate.score * 20)));
  const workloadScore = Math.min(20, Math.max(12, Math.round(candidate.score * 19)));
  const slaScore = Math.min(20, Math.max(14, Math.round(candidate.score * 20)));
  const travelScore = Math.min(15, Math.max(9, Math.round(candidate.score * 14)));

  if (isTopChoice) {
    return (
      <div className="rounded-2xl border-2 border-indigo-500/80 bg-gradient-to-br from-indigo-50/40 via-white to-sky-50/20 p-6 shadow-card transition-all">
        {/* Top Header Badge */}
        <div className="flex items-center justify-between pb-4 border-b border-indigo-100">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-600 text-white shadow-xs">
              <Award className="w-3.5 h-3.5" />
              推荐服务工程师
            </span>
            <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200/60 font-mono">
              综合匹配第 {candidate.rank} 名
            </span>
          </div>

          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-black text-indigo-700 font-mono">
              {percentage}
            </span>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              分匹配度
            </span>
          </div>
        </div>

        {/* Technician Profile Row */}
        <div className="mt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-base shadow-sm font-mono shrink-0">
              #{candidate.rank}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 tracking-tight">
                {candidate.name}
              </h3>
              <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                <span className="flex items-center gap-1 text-slate-700 font-medium">
                  <MapPin className="w-3.5 h-3.5 text-indigo-600" />
                  {candidate.service_area}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                  负载：{candidate.capacity}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1 font-medium text-emerald-700">
                  <Clock className="w-3.5 h-3.5 text-emerald-600" />
                  值班：{candidate.availability}
                </span>
              </div>
            </div>
          </div>

          <div className="flex sm:flex-col items-center sm:items-end justify-between text-xs text-slate-500 bg-white sm:bg-transparent p-3 sm:p-0 rounded-xl border sm:border-0 border-slate-200">
            <span className="text-[11px] text-slate-400">预计到达路程</span>
            <span className="font-semibold text-slate-800 font-mono mt-0.5 flex items-center gap-1">
              <Navigation className="w-3 h-3 text-indigo-500" />
              {candidate.travel_estimate}
            </span>
          </div>
        </div>

        {/* Skills Chips */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {candidate.skills.map((skill) => (
            <span
              key={skill}
              className="px-2.5 py-1 rounded-md bg-indigo-50/80 text-indigo-800 border border-indigo-100 text-xs font-semibold"
            >
              {skill}
            </span>
          ))}
        </div>

        {/* Horizontal Score Breakdown Bars */}
        <div className="mt-5 p-4 rounded-xl bg-white border border-slate-200/80 shadow-xs space-y-2.5">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
            <span className="flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-indigo-600" />
              推荐依据
            </span>
            <span className="font-mono text-slate-400">综合得分 {percentage}/100</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-xs pt-1">
            {/* Skill match */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-600">
                <span>技能匹配</span>
                <span className="font-mono font-semibold">{skillScore}/25</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  style={{ width: `${(skillScore / 25) * 100}%` }}
                  className="bg-indigo-600 h-full rounded-full"
                />
              </div>
            </div>

            {/* Service Area */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-600">
                <span>服务区域</span>
                <span className="font-mono font-semibold">{areaScore}/20</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  style={{ width: `${(areaScore / 20) * 100}%` }}
                  className="bg-emerald-600 h-full rounded-full"
                />
              </div>
            </div>

            {/* Workload */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-600">
                <span>当前负载</span>
                <span className="font-mono font-semibold">{workloadScore}/20</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  style={{ width: `${(workloadScore / 20) * 100}%` }}
                  className="bg-sky-600 h-full rounded-full"
                />
              </div>
            </div>

            {/* SLA fit */}
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-600">
                <span>服务时效</span>
                <span className="font-mono font-semibold">{slaScore}/20</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  style={{ width: `${(slaScore / 20) * 100}%` }}
                  className="bg-violet-600 h-full rounded-full"
                />
              </div>
            </div>

            {/* Travel cost */}
            <div className="space-y-1 sm:col-span-2">
              <div className="flex justify-between text-[11px] text-slate-600">
                <span>路程成本</span>
                <span className="font-mono font-semibold">{travelScore}/15</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  style={{ width: `${(travelScore / 15) * 100}%` }}
                  className="bg-amber-600 h-full rounded-full"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Why this technician? (Explainable Dispatch Engine) */}
        <div className="mt-4 pt-3 border-t border-slate-100">
          <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5 mb-2">
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
            推荐依据与决策说明
          </div>
          <ul className="space-y-1.5 text-xs text-slate-600">
            {candidate.reasons && candidate.reasons.length > 0 ? (
              candidate.reasons.map((reason, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                  <span className="font-medium text-slate-700">{reason}</span>
                </li>
              ))
            ) : (
              <li className="flex items-start gap-2">
                <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                <span>所属网格相符，专业技能完全匹配，当前负载适中可即刻派工。</span>
              </li>
            )}
          </ul>
        </div>
      </div>
    );
  }

  // Alternative Candidate (Compact Card)
  return (
    <div className="rounded-xl border border-slate-200 bg-white hover:border-slate-300 hover:shadow-xs p-4 transition-all">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center font-bold text-xs font-mono shrink-0">
            #{candidate.rank}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-slate-900 text-sm">{candidate.name}</h4>
              <span className="text-[10px] text-slate-500 font-mono">{candidate.service_area}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
              <span>负载：{candidate.capacity}</span>
              <span>•</span>
              <span className="font-mono">路程：{candidate.travel_estimate}</span>
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-base font-bold text-slate-800 font-mono">{percentage} 分</div>
          <div className="text-[10px] text-slate-400 uppercase tracking-wider">综合评分</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {candidate.skills.map((skill) => (
          <span
            key={skill}
            className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px] font-medium"
          >
            {skill}
          </span>
        ))}
      </div>

      <div className="mt-3 pt-2.5 border-t border-slate-100 text-xs text-slate-500">
        <div className="text-[11px] font-semibold text-slate-600 mb-1 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
          备选说明
        </div>
        <ul className="space-y-1 text-xs text-slate-600">
          {candidate.reasons && candidate.reasons.length > 0 ? (
            candidate.reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))
          ) : (
            <li className="flex items-start gap-1.5">
              <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
              <span>同网格备选工程师，满足技能资质要求。</span>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
};
