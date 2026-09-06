/**
 * Navigation labels and hierarchy across Customer, Operator, and Admin portals.
 */

export const navigation = {
  brand: 'FieldOps',
  platformTitle: '现场运维与智能调度平台',

  customer: {
    portalSubtitle: '客户服务中心',
    home: '首页',
    overview: '首页',
    aiAssistant: 'AI 智能报修',
    aiAssistantShort: 'AI 报修',
    myRequests: '我的工单',
    requestsShort: '工单',
    appointments: '上门预约',
    appointmentsShort: '预约',
    requestService: '提交报修',
    profile: '个人资料',
    profileShort: '我的',
    signOut: '退出登录',
    footer: 'FieldOps 智能现场运维调度平台 • 客户自助服务中心',
    operatorLink: '切换至调度中心',
  },

  operator: {
    portalSubtitle: '调度控制台',
    overview: '工作台',
    serviceRequests: '服务工单',
    appointments: '上门预约',
    escalations: '升级处理',
    systemStatus: '系统状态',
    governance: '系统治理',
    adminLink: '管理控制台',
    customerLink: '客户自助门户',
    timezone: '中国标准时间 (UTC+8)',
    userMenu: {
      profile: '调度员资料',
      signOut: '退出登录',
    },
  },

  admin: {
    portalSubtitle: '系统治理中心',
    overview: '管理概览',
    users: '用户管理',
    branches: '服务网点',
    teams: '服务班组',
    technicians: '服务工程师',
    dispatchPolicy: '派单策略',
    slaPolicy: '服务时效策略',
    integrations: '集成管理',
    audit: '审计日志',
    system: '系统状态',
    switchConsole: '控制台切换',
    operatorDashboard: '调度员工作台',
    customerPortal: '客户自助门户',
    userMenu: {
      profile: '管理员资料',
      signOut: '退出登录',
    },
  },
};
