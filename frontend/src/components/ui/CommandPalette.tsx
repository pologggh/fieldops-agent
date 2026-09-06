import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  ClipboardList,
  Calendar,
  AlertOctagon,
  Activity,
  Users,
  Wrench,
  Sliders,
  Timer,
  Network,
  ShieldCheck,
  ArrowRight,
  Command,
  Building,
  Layers,
} from 'lucide-react';

export interface CommandItem {
  id: string;
  title: string;
  subtitle?: string;
  category: '调度中心' | '系统治理' | '快捷操作';
  icon: React.ReactNode;
  path?: string;
  action?: () => void;
}

interface CommandPaletteProps {
  role?: 'operator' | 'admin' | 'viewer';
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ role = 'operator' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const operatorItems: CommandItem[] = [
    {
      id: 'nav-overview',
      title: '调度工作台',
      subtitle: '实时调度大盘、时效预警与待办行动队列',
      category: '调度中心',
      icon: <Activity className="w-4 h-4 text-indigo-600" />,
      path: '/',
    },
    {
      id: 'nav-requests',
      title: '服务工单管理',
      subtitle: '查看全量报修需求、审批流转与派工状态',
      category: '调度中心',
      icon: <ClipboardList className="w-4 h-4 text-indigo-600" />,
      path: '/service-requests',
    },
    {
      id: 'nav-appointments',
      title: '上门预约调度',
      subtitle: '查看已锁定行程、现场施工进度与日历同步',
      category: '调度中心',
      icon: <Calendar className="w-4 h-4 text-emerald-600" />,
      path: '/appointments',
    },
    {
      id: 'nav-escalations',
      title: '升级处理中心',
      subtitle: '集中处置 SLA 超时告警与调度冲突异常',
      category: '调度中心',
      icon: <AlertOctagon className="w-4 h-4 text-rose-600" />,
      path: '/escalations',
    },
    {
      id: 'nav-system',
      title: '调度中心运行状态',
      subtitle: 'PostgreSQL、Redis、发件箱与后台进程指标',
      category: '调度中心',
      icon: <Activity className="w-4 h-4 text-slate-600" />,
      path: '/system',
    },
  ];

  const adminItems: CommandItem[] = [
    {
      id: 'adm-overview',
      title: '系统治理概览',
      subtitle: '网点编制、工程师梯队与策略版本大盘',
      category: '系统治理',
      icon: <ShieldCheck className="w-4 h-4 text-rose-600" />,
      path: '/admin',
    },
    {
      id: 'adm-users',
      title: '内部用户管理',
      subtitle: '维护调度员、系统管理员与只读账号权限',
      category: '系统治理',
      icon: <Users className="w-4 h-4 text-blue-600" />,
      path: '/admin/users',
    },
    {
      id: 'adm-branches',
      title: '服务网点管理',
      subtitle: '城市服务大区、辐射范围与物理网格',
      category: '系统治理',
      icon: <Building className="w-4 h-4 text-amber-600" />,
      path: '/admin/branches',
    },
    {
      id: 'adm-teams',
      title: '服务班组管理',
      subtitle: '专业施工班组划分与班组长资质管理',
      category: '系统治理',
      icon: <Layers className="w-4 h-4 text-sky-600" />,
      path: '/admin/teams',
    },
    {
      id: 'adm-technicians',
      title: '服务工程师管理',
      subtitle: '在籍工程师花名册、资质认证与应急排班',
      category: '系统治理',
      icon: <Wrench className="w-4 h-4 text-emerald-600" />,
      path: '/admin/technicians',
    },
    {
      id: 'adm-dispatch-policy',
      title: '智能派单策略',
      subtitle: '调节工作量、距离、技能与时效匹配权重',
      category: '系统治理',
      icon: <Sliders className="w-4 h-4 text-purple-600" />,
      path: '/admin/policies/dispatch',
    },
    {
      id: 'adm-sla-policy',
      title: '服务时效策略 (SLA)',
      subtitle: '配置紧急/高/中/低各级响应时限与预警红线',
      category: '系统治理',
      icon: <Timer className="w-4 h-4 text-amber-600" />,
      path: '/admin/policies/sla',
    },
    {
      id: 'adm-integrations',
      title: '外部系统集成',
      subtitle: 'Google Calendar 排班同步与通知通道监控',
      category: '系统治理',
      icon: <Network className="w-4 h-4 text-teal-600" />,
      path: '/admin/integrations',
    },
    {
      id: 'adm-audit',
      title: '系统审计日志',
      subtitle: '关键调度与配置管理操作日志审计流',
      category: '系统治理',
      icon: <ShieldCheck className="w-4 h-4 text-slate-600" />,
      path: '/admin/audit',
    },
  ];

  const allItems = role === 'admin' ? [...operatorItems, ...adminItems] : operatorItems;

  const filteredItems = allItems.filter((item) => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      (item.subtitle && item.subtitle.toLowerCase().includes(q)) ||
      item.category.toLowerCase().includes(q)
    );
  });

  const handleSelect = (item: CommandItem) => {
    setIsOpen(false);
    if (item.path) {
      navigate(item.path);
    } else if (item.action) {
      item.action();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filteredItems.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % (filteredItems.length || 1));
    } else if (e.key === 'Enter' && filteredItems[selectedIndex]) {
      e.preventDefault();
      handleSelect(filteredItems[selectedIndex]);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50/80 hover:bg-slate-100 text-slate-500 hover:text-slate-800 text-xs font-medium transition-colors shadow-2xs"
        aria-label="快速检索或跳转"
      >
        <Search className="w-3.5 h-3.5 text-slate-400" />
        <span>快捷检索与功能跳转…</span>
        <kbd className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-200 bg-white text-[10px] font-mono text-slate-500 shadow-2xs">
          <Command className="w-2.5 h-2.5" /> K
        </kbd>
      </button>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsOpen(false);
      }}
    >
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden transform animate-in zoom-in-95 duration-150">
        {/* Search Input */}
        <div className="p-4 border-b border-slate-100 flex items-center gap-3">
          <Search className="w-5 h-5 text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="输入功能名称、页面或工单关键词搜索…"
            className="w-full text-sm font-medium text-slate-900 placeholder:text-slate-400 bg-transparent focus:outline-none"
          />
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 rounded border border-slate-200 bg-slate-50 text-[10px] font-mono text-slate-500">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 divide-y divide-slate-50">
          {filteredItems.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400">
              未找到匹配的功能页面或指令
            </div>
          ) : (
            filteredItems.map((item, idx) => (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors ${
                  idx === selectedIndex ? 'bg-indigo-50/70 text-indigo-950' : 'hover:bg-slate-50 text-slate-700'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                      idx === selectedIndex ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {item.icon}
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-slate-900 truncate flex items-center gap-2">
                      <span>{item.title}</span>
                      <span className="text-[10px] font-normal text-slate-500 px-1.5 py-0.2 rounded bg-slate-100">
                        {item.category}
                      </span>
                    </div>
                    {item.subtitle && (
                      <div className="text-[11px] text-slate-500 truncate mt-0.5">{item.subtitle}</div>
                    )}
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-2" />
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1 py-0.5 rounded border border-slate-200 bg-white font-mono text-[10px]">
                ↑
              </kbd>{' '}
              <kbd className="px-1 py-0.5 rounded border border-slate-200 bg-white font-mono text-[10px]">
                ↓
              </kbd>{' '}
              切换选项
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded border border-slate-200 bg-white font-mono text-[10px]">
                ↵
              </kbd>{' '}
              确认跳转
            </span>
          </div>
          <span className="text-slate-400">安全页面导航</span>
        </div>
      </div>
    </div>
  );
};
