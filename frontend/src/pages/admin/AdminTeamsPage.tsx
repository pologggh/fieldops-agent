import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  Building2,
  Wrench,
  UserCheck,
  ShieldCheck,
  Plus,
} from 'lucide-react';
import { branches, teams, ServiceBranch, ServiceTeam, getServiceTypeText } from '../../locales';
import { getAdminTechnicians } from '../../api/adminApi';

export const AdminTeamsPage: React.FC = () => {
  const { data: technicians } = useQuery({
    queryKey: ['admin-technicians'],
    queryFn: getAdminTechnicians,
  });

  const techList = technicians || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">服务班组管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            按专业维修工种、所属网点组建作业班组，设定班组长与派工调度优先级。
          </p>
        </div>
        <button
          type="button"
          onClick={() => alert('已连接班组中枢。系统当前班组作业正常。')}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          创建服务班组
        </button>
      </div>

      {/* Grid of Teams */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {teams.map((tm: ServiceTeam) => {
          const branch = branches.find((b: ServiceBranch) => b.id === tm.branchId) || branches[0];
          const members = techList.filter((tech) => tm.memberTechnicianIds.includes(tech.id));

          return (
            <div
              key={tm.id}
              className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card hover:shadow-md transition-shadow space-y-4"
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{tm.name}</h3>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                      <Building2 className="w-3.5 h-3.5 text-slate-400" />
                      <span>{branch.name}</span>
                    </div>
                  </div>
                </div>

                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                  <ShieldCheck className="w-3 h-3" />
                  值班在岗
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="text-slate-400 block mb-1">专业维修品类</span>
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <Wrench className="w-3.5 h-3.5 text-indigo-600" />
                    {getServiceTypeText(tm.trade)}
                  </span>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="text-slate-400 block mb-1">带班班组长</span>
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-emerald-600" />
                    {tm.leader}
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 space-y-2 text-xs">
                <div className="flex items-center justify-between text-slate-500">
                  <span>班组成员名单 ({tm.memberTechnicianIds.length} 名持证工程师)：</span>
                  <Link
                    to="/admin/technicians"
                    className="text-indigo-600 hover:text-indigo-800 font-semibold"
                  >
                    配置班组 →
                  </Link>
                </div>

                <div className="flex flex-wrap gap-2 pt-1">
                  {members.length > 0 ? (
                    members.map((m) => (
                      <span
                        key={m.id}
                        className="px-2.5 py-1 rounded-lg bg-indigo-50/80 border border-indigo-200/60 text-indigo-900 font-medium text-xs flex items-center gap-1.5"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
                        {m.name} (#{m.id})
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-400 italic">工程师：{tm.leader} 及轮值学员</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
