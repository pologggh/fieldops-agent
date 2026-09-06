import React, { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  MapPin,
  Compass,
  Navigation,
  Layers,
  Wrench,
  Zap,
  Droplets,
  Radio,
  Clock,
  User,
  ShieldAlert,
  ArrowRight,
  Maximize2,
  Minimize2,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Truck,
  Building2,
  Filter,
} from 'lucide-react';
import { ServiceRequestListItem } from '../../types/api';
import { branches, teams, ServiceBranch } from '../../locales/branchesTeams';
import { StatusBadge } from '../ui';
import { getServiceTypeText, getUrgencyText } from '../../locales';
import { formatDateTimeZh } from '../../utils/dateTime';

interface DispatchMapViewProps {
  requests: ServiceRequestListItem[];
  onSelectRequest?: (req: ServiceRequestListItem) => void;
}

// Coordinate mapping for branches on the 1000x600 operational canvas
interface GeoNode {
  id: string;
  name: string;
  code: string;
  region: string;
  x: number;
  y: number;
  coverage: string;
  address: string;
  capacityRate: number;
}

interface TechnicianPin {
  id: number;
  name: string;
  branchId: string;
  trade: string;
  status: 'available' | 'traveling' | 'working';
  x: number;
  y: number;
  phone: string;
  activeTaskId?: number;
}

const REGION_BOUNDS: Record<string, GeoNode> = {
  GZ_TH: {
    id: 'GZ_TH',
    name: '广州天河服务中心',
    code: 'GZ-TH-01',
    region: '华南粤港澳大湾区',
    x: 280,
    y: 420,
    coverage: '天河区、越秀区、海珠区',
    address: '广州市天河区天河路 388 号',
    capacityRate: 78,
  },
  SZ_NS: {
    id: 'SZ_NS',
    name: '深圳南山服务中心',
    code: 'SZ-NS-01',
    region: '华南粤港澳大湾区',
    x: 360,
    y: 470,
    coverage: '南山区、福田区、宝安区',
    address: '深圳市南山区科技园科发路 18 号',
    capacityRate: 85,
  },
  SH_PD: {
    id: 'SH_PD',
    name: '上海浦东服务中心',
    code: 'SH-PD-01',
    region: '华东长三角核心区',
    x: 740,
    y: 320,
    coverage: '浦东新区、黄浦区、徐汇区',
    address: '上海市浦东新区张江高科祖冲之路 88 号',
    capacityRate: 92,
  },
  BJ_HD: {
    id: 'BJ_HD',
    name: '北京海淀服务中心',
    code: 'BJ-HD-01',
    region: '华北京津冀枢纽区',
    x: 620,
    y: 150,
    coverage: '海淀区、朝阳区、西城区',
    address: '北京市海淀区中关村南大街 1 号',
    capacityRate: 64,
  },
};

const TECHNICIANS: TechnicianPin[] = [
  {
    id: 1,
    name: '陈志强',
    branchId: 'GZ_TH',
    trade: '暖通空调',
    status: 'available',
    x: 295,
    y: 395,
    phone: '138-0020-0001',
  },
  {
    id: 2,
    name: '王大伟',
    branchId: 'GZ_TH',
    trade: '家电维保',
    status: 'working',
    x: 250,
    y: 430,
    phone: '138-0020-0002',
    activeTaskId: 102,
  },
  {
    id: 3,
    name: '刘伟',
    branchId: 'GZ_TH',
    trade: '给排水工程',
    status: 'traveling',
    x: 310,
    y: 445,
    phone: '138-0020-0003',
  },
  {
    id: 4,
    name: '李建军',
    branchId: 'SZ_NS',
    trade: '强弱电工程',
    status: 'available',
    x: 375,
    y: 455,
    phone: '139-0755-0004',
  },
  {
    id: 5,
    name: '张明海',
    branchId: 'BJ_HD',
    trade: '弱电网络',
    status: 'available',
    x: 635,
    y: 135,
    phone: '136-0010-0005',
  },
];

export const DispatchMapView: React.FC<DispatchMapViewProps> = ({
  requests,
  onSelectRequest,
}) => {
  const navigate = useNavigate();
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(
    requests.length > 0 ? requests[0].id : null
  );
  const [activeRegion, setActiveRegion] = useState<string>('all');
  const [showBranches, setShowBranches] = useState(true);
  const [showTechnicians, setShowTechnicians] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [isFullScreen, setIsFullScreen] = useState(false);

  // Map requests to coordinate anchors around their nearest branch
  const requestPins = useMemo(() => {
    return requests.map((req, idx) => {
      // Determine nearest branch based on location text or cycle through branches
      let branchKey = 'GZ_TH';
      const loc = (req.location || '').toLowerCase();
      if (loc.includes('深圳') || loc.includes('南山') || loc.includes('福田')) {
        branchKey = 'SZ_NS';
      } else if (loc.includes('上海') || loc.includes('浦东') || loc.includes('黄浦')) {
        branchKey = 'SH_PD';
      } else if (loc.includes('北京') || loc.includes('海淀') || loc.includes('朝阳')) {
        branchKey = 'BJ_HD';
      } else {
        const keys = Object.keys(REGION_BOUNDS);
        branchKey = keys[idx % keys.length];
      }

      const branch = REGION_BOUNDS[branchKey];
      // Deterministic spread around branch node
      const angle = ((idx * 57 + req.id * 31) % 360) * (Math.PI / 180);
      const radius = 35 + ((req.id * 17) % 55);
      const x = Math.round(branch.x + Math.cos(angle) * radius);
      const y = Math.round(branch.y + Math.sin(angle) * radius);

      return {
        ...req,
        branchKey,
        branch,
        x,
        y,
      };
    });
  }, [requests]);

  const activePin = useMemo(() => {
    return requestPins.find((p) => p.id === selectedRequestId) || requestPins[0] || null;
  }, [requestPins, selectedRequestId]);

  // Nearest technician to active pin
  const nearestTechnician = useMemo(() => {
    if (!activePin) return null;
    const sameBranchTechs = TECHNICIANS.filter((t) => t.branchId === activePin.branchKey);
    if (sameBranchTechs.length > 0) {
      return sameBranchTechs[0];
    }
    return TECHNICIANS[0];
  }, [activePin]);

  const handlePinClick = (req: ServiceRequestListItem) => {
    setSelectedRequestId(req.id);
    if (onSelectRequest) {
      onSelectRequest(req);
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'emergency':
        return '#ef4444'; // Red
      case 'high':
        return '#f97316'; // Amber
      case 'medium':
        return '#3b82f6'; // Blue
      default:
        return '#64748b'; // Slate
    }
  };

  return (
    <div
      className={`bg-slate-950 text-white rounded-2xl border border-slate-800 shadow-xl overflow-hidden flex flex-col transition-all duration-300 ${
        isFullScreen ? 'fixed inset-4 z-50 rounded-2xl' : 'w-full'
      }`}
    >
      {/* Top Map Operations Command Bar */}
      <div className="px-5 py-3.5 bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100 tracking-wide">
                GIS 智能调度大屏 · 全国网格作业全景
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/60">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping mr-1" />
                网格实时在线
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              覆盖全国 4 大网点基站 · 联动 {TECHNICIANS.length} 名在岗工程师 · 实时监控 {requests.length} 笔调度工单
            </p>
          </div>
        </div>

        {/* View & Layer Switches */}
        <div className="flex items-center flex-wrap gap-2 text-xs">
          {/* Layer toggles */}
          <div className="flex items-center bg-slate-800/80 border border-slate-700/60 rounded-xl p-0.5">
            <button
              type="button"
              onClick={() => setShowBranches((v) => !v)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                showBranches ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              网点基站
            </button>
            <button
              type="button"
              onClick={() => setShowTechnicians((v) => !v)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                showTechnicians ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              在岗工程师
            </button>
            <button
              type="button"
              onClick={() => setShowRoutes((v) => !v)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                showRoutes ? 'bg-indigo-600 text-white shadow-xs' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              调度航线
            </button>
          </div>

          <button
            type="button"
            onClick={() => setIsFullScreen((v) => !v)}
            className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            title={isFullScreen ? '退出全屏' : '全屏展示'}
          >
            {isFullScreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main Map Body (Vector SVG Canvas + Floating Inspector Card) */}
      <div className="relative flex-1 min-h-[540px] max-h-[720px] bg-slate-950 overflow-hidden flex">
        {/* SVG Vector Map Canvas */}
        <div className="w-full h-full relative overflow-hidden flex items-center justify-center">
          <svg
            viewBox="0 0 1000 600"
            className="w-full h-full object-contain select-none"
            style={{ filter: 'drop-shadow(0 0 20px rgba(0,0,0,0.5))' }}
          >
            <defs>
              {/* Radial gradient background */}
              <radialGradient id="grid-glow" cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="#1e1b4b" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#020617" stopOpacity="0.9" />
              </radialGradient>

              {/* Dot Grid Pattern */}
              <pattern id="dot-grid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                <circle cx="20" cy="20" r="1" fill="#334155" fillOpacity="0.4" />
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" strokeOpacity="0.3" />
              </pattern>

              {/* Animated Route Pulse */}
              <linearGradient id="route-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="50%" stopColor="#38bdf8" />
                <stop offset="100%" stopColor="#ec4899" />
              </linearGradient>
            </defs>

            {/* Base Background & Coordinates Grid */}
            <rect width="1000" height="600" fill="url(#grid-glow)" />
            <rect width="1000" height="600" fill="url(#dot-grid)" />

            {/* Regional Map Boundaries & Service Hexagons */}
            {/* North Hub Region (Beijing) */}
            <path
              d="M 520 80 L 720 70 L 760 210 L 560 230 Z"
              fill="#1e293b"
              fillOpacity="0.25"
              stroke="#334155"
              strokeWidth="1.2"
              strokeDasharray="4 4"
            />
            <text x="540" y="105" fill="#64748b" fontSize="12" fontWeight="600" letterSpacing="2">
              华北京津冀区域网格
            </text>

            {/* East Hub Region (Shanghai) */}
            <path
              d="M 640 240 L 840 220 L 870 410 L 680 420 Z"
              fill="#1e293b"
              fillOpacity="0.25"
              stroke="#334155"
              strokeWidth="1.2"
              strokeDasharray="4 4"
            />
            <text x="690" y="265" fill="#64748b" fontSize="12" fontWeight="600" letterSpacing="2">
              华东长三角区域网格
            </text>

            {/* South Hub Region (Guangdong-GZ/SZ) */}
            <path
              d="M 180 340 L 450 320 L 460 550 L 190 560 Z"
              fill="#1e293b"
              fillOpacity="0.25"
              stroke="#334155"
              strokeWidth="1.2"
              strokeDasharray="4 4"
            />
            <text x="210" y="365" fill="#64748b" fontSize="12" fontWeight="600" letterSpacing="2">
              华南粤港澳大湾区网格
            </text>

            {/* Hub Interconnection Trunk Lines */}
            <path
              d="M 280 420 Q 500 380 740 320"
              fill="none"
              stroke="#4338ca"
              strokeWidth="1.5"
              strokeDasharray="6 6"
              strokeOpacity="0.4"
            />
            <path
              d="M 620 150 Q 690 220 740 320"
              fill="none"
              stroke="#4338ca"
              strokeWidth="1.5"
              strokeDasharray="6 6"
              strokeOpacity="0.4"
            />

            {/* Dynamic Dispatch Route Vectors for Selected Request */}
            {showRoutes && activePin && nearestTechnician && (
              <g className="transition-all duration-500">
                {/* Branch to Technician Commute Line */}
                <line
                  x1={activePin.branch.x}
                  y1={activePin.branch.y}
                  x2={nearestTechnician.x}
                  y2={nearestTechnician.y}
                  stroke="#6366f1"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  strokeOpacity="0.7"
                />

                {/* Technician to Request Site Line */}
                <line
                  x1={nearestTechnician.x}
                  y1={nearestTechnician.y}
                  x2={activePin.x}
                  y2={activePin.y}
                  stroke="url(#route-gradient)"
                  strokeWidth="2.5"
                  strokeDasharray="6 4"
                />

                {/* Commute Distance & ETA Tag */}
                <g
                  transform={`translate(${Math.round((nearestTechnician.x + activePin.x) / 2)}, ${Math.round(
                    (nearestTechnician.y + activePin.y) / 2 - 14
                  )})`}
                >
                  <rect
                    x="-42"
                    y="-11"
                    width="84"
                    height="22"
                    rx="11"
                    fill="#0f172a"
                    stroke="#6366f1"
                    strokeWidth="1"
                    fillOpacity="0.95"
                  />
                  <text
                    x="0"
                    y="3"
                    fill="#38bdf8"
                    fontSize="10"
                    fontWeight="700"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    3.4km · 14分
                  </text>
                </g>
              </g>
            )}

            {/* Branch Hub Station Nodes */}
            {showBranches &&
              Object.values(REGION_BOUNDS).map((branch) => {
                const isCurrentActive = activePin?.branchKey === branch.id;
                return (
                  <g key={branch.id} className="cursor-pointer">
                    {/* Pulsing Radar Ring */}
                    <circle
                      cx={branch.x}
                      cy={branch.y}
                      r="28"
                      fill="#6366f1"
                      fillOpacity={isCurrentActive ? 0.2 : 0.08}
                      stroke="#818cf8"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <circle
                      cx={branch.x}
                      cy={branch.y}
                      r="14"
                      fill={isCurrentActive ? '#4f46e5' : '#1e1b4b'}
                      stroke="#a5b4fc"
                      strokeWidth="2"
                    />
                    <circle cx={branch.x} cy={branch.y} r="5" fill="#ffffff" />

                    {/* Branch Label */}
                    <rect
                      x={branch.x - 55}
                      y={branch.y + 18}
                      width="110"
                      height="20"
                      rx="6"
                      fill="#090d16"
                      stroke="#334155"
                      strokeWidth="1"
                      fillOpacity="0.9"
                    />
                    <text
                      x={branch.x}
                      y={branch.y + 32}
                      fill="#e2e8f0"
                      fontSize="10"
                      fontWeight="600"
                      textAnchor="middle"
                    >
                      {branch.name}
                    </text>
                  </g>
                );
              })}

            {/* In-Field Technicians Nodes */}
            {showTechnicians &&
              TECHNICIANS.map((tech) => {
                const isAssigned = nearestTechnician?.id === tech.id;
                return (
                  <g key={tech.id} className="cursor-pointer group">
                    <circle
                      cx={tech.x}
                      cy={tech.y}
                      r={isAssigned ? 13 : 10}
                      fill={tech.status === 'available' ? '#065f46' : '#92400e'}
                      stroke={isAssigned ? '#38bdf8' : '#34d399'}
                      strokeWidth={isAssigned ? 2.5 : 1.5}
                    />
                    <circle
                      cx={tech.x}
                      cy={tech.y}
                      r="3"
                      fill="#ffffff"
                    />
                    {/* Tech Name Pin */}
                    <text
                      x={tech.x}
                      y={tech.y - 12}
                      fill={isAssigned ? '#38bdf8' : '#cbd5e1'}
                      fontSize="9"
                      fontWeight="700"
                      textAnchor="middle"
                    >
                      {tech.name}
                    </text>
                  </g>
                );
              })}

            {/* Service Request Pins */}
            {requestPins.map((req) => {
              const isSelected = req.id === selectedRequestId;
              const color = getUrgencyColor(req.urgency);

              return (
                <g
                  key={req.id}
                  onClick={() => handlePinClick(req)}
                  className="cursor-pointer group transition-transform hover:scale-125"
                  transform={`translate(${req.x}, ${req.y})`}
                >
                  {/* Selected Ripple Ring */}
                  {isSelected && (
                    <circle
                      r="20"
                      fill={color}
                      fillOpacity="0.25"
                      stroke={color}
                      strokeWidth="1.5"
                    >
                      <animate
                        attributeName="r"
                        values="14;24;14"
                        dur="2s"
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="stroke-opacity"
                        values="1;0.2;1"
                        dur="2s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}

                  {/* Marker Body */}
                  <circle
                    r={isSelected ? 10 : 8}
                    fill={color}
                    stroke="#ffffff"
                    strokeWidth={isSelected ? 2.5 : 1.5}
                  />

                  <text
                    y="3.5"
                    fill="#ffffff"
                    fontSize="8"
                    fontWeight="800"
                    textAnchor="middle"
                  >
                    #{req.id}
                  </text>

                  {/* Tooltip on hover */}
                  <g className="opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <rect
                      x="-50"
                      y="-32"
                      width="100"
                      height="20"
                      rx="4"
                      fill="#0f172a"
                      stroke="#475569"
                      strokeWidth="1"
                    />
                    <text
                      x="0"
                      y="-18"
                      fill="#f8fafc"
                      fontSize="9"
                      textAnchor="middle"
                      fontWeight="600"
                    >
                      {req.customer_name} · {getServiceTypeText(req.service_type)}
                    </text>
                  </g>
                </g>
              );
            })}
          </svg>

          {/* Map Corner Legend */}
          <div className="absolute bottom-4 left-4 p-3 rounded-xl bg-slate-900/90 border border-slate-800 backdrop-blur-md text-[11px] space-y-1.5 shadow-lg pointer-events-auto">
            <div className="font-bold text-slate-300 pb-1 border-b border-slate-800 flex items-center justify-between gap-4">
              <span>GIS 地图图例</span>
              <Compass className="w-3.5 h-3.5 text-indigo-400" />
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 border border-white" />
              <span>网点调度基站 (4 座)</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-white" />
              <span>在岗工程师 (空闲)</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 border border-white" />
              <span>紧急报修 (P0 / Emergency)</span>
            </div>
            <div className="flex items-center gap-2 text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 border border-white" />
              <span>高优先报修 (P1 / High)</span>
            </div>
          </div>
        </div>

        {/* Selected Request Inspector Floating Side Card */}
        {activePin && (
          <div className="w-80 md:w-96 bg-slate-900/95 border-l border-slate-800 p-5 overflow-y-auto shrink-0 flex flex-col justify-between backdrop-blur-md">
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-indigo-400 text-sm">
                    #{activePin.id}
                  </span>
                  <StatusBadge type="status" value={activePin.status} />
                </div>
                <StatusBadge type="urgency" value={activePin.urgency} />
              </div>

              {/* Service Info */}
              <div className="space-y-2">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Wrench className="w-4 h-4 text-indigo-400" />
                  {getServiceTypeText(activePin.service_type)}
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
                  {activePin.raw_message || '客户申报设备故障，待调度中心分派工程师前往现场检修。'}
                </p>
              </div>

              {/* Customer & Location */}
              <div className="space-y-2 text-xs bg-slate-800/40 p-3 rounded-xl border border-slate-750">
                <div className="flex items-center gap-2 text-slate-300">
                  <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="font-semibold text-white">{activePin.customer_name}</span>
                  <span className="text-slate-500 font-mono text-[11px]">
                    ({activePin.customer_phone || '未留电话'})
                  </span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{activePin.location || '待确认现场地址'}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span>申报时间：{formatDateTimeZh(activePin.created_at)}</span>
                </div>
              </div>

              {/* Recommended Dispatch Match */}
              {nearestTechnician && (
                <div className="bg-gradient-to-br from-indigo-950/60 to-slate-900 p-3.5 rounded-xl border border-indigo-900/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-indigo-300 flex items-center gap-1.5">
                      <Navigation className="w-3.5 h-3.5 text-indigo-400" />
                      推荐就近工程师
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800/50">
                      匹配度 96%
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <div>
                      <span className="font-bold text-slate-100 text-sm block">
                        {nearestTechnician.name}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {nearestTechnician.trade} · 归属 {activePin.branch.name}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-mono font-bold text-sky-400 block">
                        约 3.4 公里
                      </span>
                      <span className="text-[10px] text-slate-500">预计 14 分钟到场</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Action Footer */}
            <div className="pt-4 border-t border-slate-800 space-y-2">
              <Link
                to={`/service-requests/${activePin.id}`}
                className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md transition-colors"
              >
                进入调度详情决策
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
