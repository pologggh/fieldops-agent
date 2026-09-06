/**
 * Admin Console localized strings (Governance, configuration, fleet, policy, and audit).
 */

export const admin = {
  overview: {
    pageTitle: '系统治理概览',
    pageSubtitle: '全局把控服务网点编制、工程师梯队、派单与时效策略版本及集成健康度。',
    refreshBtn: '刷新治理指标',
    stats: {
      users: '平台活跃用户',
      branches: '服务网点数',
      teams: '专业服务班组',
      technicians: '在籍服务工程师',
      activePolicies: '当前生效策略',
      systemHealth: '基础设施状态',
    },
    cards: {
      orgTitle: '组织架构与工程师分布',
      policyTitle: '运行中决策策略版本',
      integrationTitle: '外联集成与通道状态',
      recentAuditTitle: '近期系统管理审计日志',
      viewAll: '进入管理',
    },
  },

  users: {
    pageTitle: '内部用户管理',
    pageSubtitle: '维护调度员、系统管理员及只读审计用户的权限角色与账号状态。',
    createBtn: '新增内部用户',
    table: {
      name: '姓名',
      email: '账号 (登录邮箱)',
      role: '角色权限',
      status: '账号状态',
      lastLogin: '最后登录时间',
      createdAt: '创建时间',
      actions: '操作',
      activate: '启用账号',
      deactivate: '停用账号',
      changeRole: '调整角色',
    },
    modal: {
      createTitle: '创建内部用户',
      nameLabel: '用户姓名 *',
      emailLabel: '登录邮箱 *',
      roleLabel: '角色权限 *',
      passwordLabel: '初始登录密码 *',
      confirmCreate: '确认创建',
      deactivateTitle: '确认停用该用户？',
      deactivateDesc: '停用后该用户将立即无法登录调度平台。',
    },
  },

  branches: {
    pageTitle: '服务网点管理',
    pageSubtitle: '划分城市服务大区与线下驻点，统筹辖区覆盖范围、专业班组及工程师力量。',
    createBtn: '新增服务网点',
    table: {
      name: '网点名称',
      code: '网点编码',
      region: '所在行政区',
      coverage: '服务辐射范围',
      teamCount: '班组数量',
      techCount: '工程师编制',
      status: '营运状态',
      actions: '操作',
    },
  },

  teams: {
    pageTitle: '服务班组管理',
    pageSubtitle: '按专业工种细分现场作业执行单元，指派班组长并负责技能与日常排班。',
    createBtn: '新增服务班组',
    table: {
      name: '班组名称',
      branch: '所属网点',
      leader: '班组负责人',
      skills: '主营专业',
      members: '班组成员数',
      status: '作业状态',
      actions: '操作',
    },
  },

  technicians: {
    pageTitle: '服务工程师管理',
    pageSubtitle: '维护现场技术工程师花名册、资质认证、所属网点、班组归属及应急排班。',
    createBtn: '录入工程师',
    table: {
      id: '工号',
      name: '姓名',
      branch: '所属网点',
      team: '所属班组',
      skills: '资质技能',
      workload: '当前负荷',
      emergencyDuty: '应急值班',
      status: '在岗状态',
      actions: '操作',
      edit: '编辑档案',
      activate: '恢复在岗',
      deactivate: '离岗停工',
    },
    modal: {
      createTitle: '新增服务工程师档案',
      editTitle: '编辑服务工程师档案',
      nameLabel: '工程师姓名 *',
      branchLabel: '所属服务网点 *',
      skillsLabel: '持有专业技能 *',
      maxJobsLabel: '每日工单上限 (单/日) *',
      maxMinutesLabel: '每日作业工时上限 (分钟) *',
      emergencyLabel: '支持应急派单响应',
      submitBtn: '保存档案',
    },
  },

  dispatchPolicy: {
    pageTitle: '智能派单策略配置',
    pageSubtitle: '调节匹配工程师时的权重系数，平衡服务时效、工作负荷、技能贴合度与路程成本。',
    activeBadge: '当前生效版本：v{version}',
    saveDraftBtn: '保存并发布新策略版本',
    weights: {
      title: '派单权重因子调节',
      workloadWeight: '工作负载均衡权重 (Workload)',
      workloadDesc: '权重越高，越优先派给当前在手任务较少的工程师。',
      capacityWeight: '剩余产能匹配权重 (Capacity)',
      capacityDesc: '权重越高，越倾向于保护即将超出单日作业上限的工程师。',
      slaWeight: '服务时效紧急度权重 (SLA Fit)',
      slaDesc: '权重越高，越优先指派能最快到达以满足 SLA 要求的工程师。',
      travelWeight: '路程时间与距离权重 (Travel Distance)',
      travelDesc: '权重越高，越优先指派物理距离最近或通勤成本最低的工程师。',
      overtimePenalty: '跨区/超时作业惩罚因子 (Overtime Penalty)',
      overtimeDesc: '对超出标准工作时段或跨区域作业实施的惩罚抵扣分值。',
    },
    diff: {
      title: '版本变更比对 (Diff Preview)',
      noChange: '策略参数与当前运行版本一致，暂无变动。',
      changed: '已识别到参数调整：',
    },
    history: {
      title: '历史策略版本归档',
      versionCol: '策略版本',
      statusCol: '状态',
      creatorCol: '发布操作人',
      timeCol: '生效时间',
      viewDiffBtn: '查看版本明细',
    },
  },

  slaPolicy: {
    pageTitle: '服务时效策略配置 (SLA)',
    pageSubtitle: '按紧急程度阶梯设定响应时限、派单确认时限、到达时限与临期预警红线。',
    activeBadge: '当前生效版本：v{version}',
    saveBtn: '发布新 SLA 策略',
    tiers: {
      emergency: '紧急报修 (Emergency)',
      high: '高优工单 (High)',
      medium: '普通服务 (Medium)',
      low: '常规保养 (Low)',
      responseMinutes: '初次响应时限 (分钟)',
      assignmentMinutes: '派单锁定限时 (分钟)',
      serviceStartMinutes: '工程师到场限时 (分钟)',
      atRiskThreshold: '临期预警阈值 (提前分钟数)',
    },
  },

  integrations: {
    pageTitle: '外部系统集成管理',
    pageSubtitle: '监控 Google Calendar 工程师排班同步及各类企业级通知管道运转状况。',
    refreshBtn: '检测集成连接',
    providers: {
      googleCalendar: {
        name: 'Google Calendar (工程师排班日历)',
        desc: '双向同步技术人员上门日程，防止时间冲突与跨平台排班割裂。',
      },
      outbox: {
        name: '事务型发件箱 (Transactional Outbox)',
        desc: '保障在网络闪断或异步作业故障时，通知与事件投递具备最终一致性。',
      },
    },
    status: {
      healthy: '运行正常',
      warning: '需要关注',
      error: '连接异常',
      retryBtn: '重试失败队列',
    },
  },

  audit: {
    pageTitle: '系统审计日志',
    pageSubtitle: '完整记录调度派工、策略版本发布、用户启停等关键管理操作的操作人与变更明细。',
    refreshBtn: '刷新审计记录',
    table: {
      time: '操作时间',
      actor: '操作人',
      action: '操作类型',
      entity: '影响对象',
      status: '执行结果',
      details: '操作详情',
    },
  },

  system: {
    pageTitle: '系统底层遥测与健康度',
    pageSubtitle: '核心 API 服务实例、数据库连接池、分布式缓存与后台定时工作进程实时指标。',
  },
};
