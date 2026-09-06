/**
 * Unified status dictionaries across ServiceRequests, Appointments,
 * Assignments, SLA, Roles, Severities, and Integrations.
 */

export const status = {
  // 1. Service Request Status
  serviceRequest: {
    received: '待受理',
    created: '待受理',
    submitted: '待受理',
    validated: '待受理',
    open: '待受理',
    needs_information: '待补充信息',
    pending_dispatch: '待派单',
    pending_acceptance: '待接单',
    assigned: '已派单',
    pending_appointment: '待预约',
    ready_for_scheduling: '待预约',
    matched: '待预约',
    waiting_for_approval: '待确认派单',
    ready_for_review: '待确认派单',
    approved: '待预约',
    scheduled: '已预约',
    appointment_created: '已预约',
    reschedule_requested: '改期处理中',
    needs_rescheduling: '改期协商中',
    conflict: '改期协商中',
    in_progress: '服务中',
    pending_completion_confirmation: '待确认完工',
    completed: '已完成',
    resolved: '已完成',
    cancelled: '已取消',
    canceled: '已取消',
    rejected: '已拒绝',
    escalated: '升级处理中',
  },

  // 2. Appointment Status
  appointment: {
    proposed: '待确认',
    scheduled: '已预约',
    confirmed: '已确认',
    in_progress: '服务中',
    completed: '已完成',
    cancelled: '已取消',
    canceled: '已取消',
    reschedule_requested: '改期处理中',
    pending: '待确认',
  },

  // 3. Assignment Status
  assignment: {
    pending: '待接单',
    accepted: '已接单',
    rejected: '已拒单',
    superseded: '已改派',
    cancelled: '已取消',
    completed: '已完成',
  },

  // 4. SLA Adherence Status
  sla: {
    on_track: '正常',
    at_risk: '即将超时',
    breached: '已超时',
    completed: '已达成',
  },

  // 5. System Roles
  role: {
    admin: '管理员',
    operator: '调度员',
    viewer: '只读用户',
    customer: '客户',
  },

  // 6. Escalation Severity
  severity: {
    critical: '紧急',
    high: '高',
    medium: '普通',
    low: '低',
  },

  // 7. Integration & System Status
  integration: {
    healthy: '运行正常',
    running: '运行正常',
    synced: '同步正常',
    active: '已启用',
    warning: '需要处理',
    at_risk: '需要处理',
    pending: '待处理',
    failed: '配置异常',
    error: '运行异常',
    disabled: '已停用',
    inactive: '已停用',
    cancelled: '已取消',
  },

  // 8. Calm Status Projection for Customers (Customer Portal)
  calmStatus: {
    received: {
      title: '待受理',
      desc: '调度中心已收到您的报修需求，正在审核评估。',
      color: 'text-indigo-700 bg-indigo-50 border-indigo-200',
    },
    validated: {
      title: '待受理',
      desc: '调度中心已核实需求，即将为您调度专业人员。',
      color: 'text-indigo-700 bg-indigo-50 border-indigo-200',
    },
    matched: {
      title: '待预约',
      desc: '已匹配附近服务网点，正在协商锁定最佳上门时间段。',
      color: 'text-purple-700 bg-purple-50 border-purple-200',
    },
    waiting_for_approval: {
      title: '待确认派单',
      desc: '服务方案已生成，调度员正在核准排班与技能匹配度。',
      color: 'text-purple-700 bg-purple-50 border-purple-200',
    },
    ready_for_review: {
      title: '待确认派单',
      desc: '服务方案已生成，调度员正在核准排班与技能匹配度。',
      color: 'text-purple-700 bg-purple-50 border-purple-200',
    },
    scheduled: {
      title: '已预约',
      desc: '已为您锁定专属服务工程师及上门时间段。',
      color: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    },
    in_progress: {
      title: '服务中',
      desc: '工程师已到达现场并正在展开检修排查作业。',
      color: 'text-sky-700 bg-sky-50 border-sky-200',
    },
    pending_completion_confirmation: {
      title: '待确认完工',
      desc: '工程师已完成现场施工，等待您的服务验收与确认。',
      color: 'text-amber-700 bg-amber-50 border-amber-200',
    },
    completed: {
      title: '已完成',
      desc: '现场维修作业完工并已通过客户验收。',
      color: 'text-slate-700 bg-slate-100 border-slate-200',
    },
    reschedule_requested: {
      title: '改期处理中',
      desc: '改期申请已受理，原预约在锁定新时间前保持有效。',
      color: 'text-amber-800 bg-amber-50 border-amber-200',
    },
    cancelled: {
      title: '已取消',
      desc: '该服务工单已终止受理。',
      color: 'text-slate-600 bg-slate-100 border-slate-200',
    },
    default: {
      title: '处理中',
      desc: '您的服务工单正在按流程推进中。',
      color: 'text-slate-700 bg-slate-50 border-slate-200',
    },
  },
};
