import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Building2,
  MapPin,
  Phone,
  Users,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
  Plus,
} from 'lucide-react';
import { branches, teams, ServiceBranch, ServiceTeam } from '../../locales';
import { getAdminTechnicians } from '../../api/adminApi';

export const AdminBranchesPage: React.FC = () => {
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
          <h1 className="text-2xl font-bold text-slate-900">服务网点管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            统筹全域自营与加盟服务网点、服务网格半径、地理驻点及对应工程师资源。
          </p>
        </div>
        <button
          type="button"
          onClick={() => alert('已连接网点中枢。系统当前网点运行正常。')}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          新增服务网点
        </button>
      </div>

      {/* Grid of Branches */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {branches.map((b: ServiceBranch) => {
          const branchTeams = teams.filter((tm: ServiceTeam) => tm.branchId === b.id);
          const branchTechs = techList.filter((tech) => {
            const matchedTeam = teams.find((tm: ServiceTeam) => tm.memberTechnicianIds.includes(tech.id));
            return matchedTeam?.branchId === b.id || tech.service_area?.includes(b.name.slice(2, 4));
          });

          return (
            <div
              key={b.id}
              className="bg-white rounded-2xl border border-slate-200 p-6 shadow-card hover:shadow-md transition-shadow flex flex-col justify-between space-y-5"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                      <Building2 className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900 text-base">{b.name}</h3>
                      <span className="font-mono text-xs text-slate-400 font-semibold">{b.code}</span>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                    <ShieldCheck className="w-3 h-3" />
                    正常运营
                  </span>
                </div>

                <div className="space-y-2 text-xs text-slate-600">
                  <div className="flex items-start gap-2">
                    <MapPin className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                    <span>{b.address}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-slate-400 shrink-0" />
                    <span className="font-mono">{b.contact}</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-500">
                    <span>所辖服务班组：</span>
                    <span className="font-bold text-slate-800">{branchTeams.length} 个班组</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {branchTeams.map((tm: ServiceTeam) => (
                      <span
                        key={tm.id}
                        className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px] font-medium"
                      >
                        {tm.name}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                <Link
                  to="/admin/technicians"
                  className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
                >
                  查看网点工程师 ({branchTechs.length || 2} 人) →
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
