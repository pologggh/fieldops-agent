/**
 * Service Types, Urgencies, Skills, Branches, and Teams in Chinese.
 */

export const service = {
  // Service Trade Categories
  types: {
    HVAC: '空调 / 暖通维修',
    'HVAC Repair & Heating': '空调 / 暖通与供暖',
    Plumbing: '水管维修',
    'Plumbing & Leaks': '水管及漏水维修',
    Electrical: '电气维修',
    'Electrical & Wiring': '电路及配电系统',
    Networking: '网络维护',
    'Appliance Repair': '家电维修',
    'Appliance Maintenance': '大型家电设备维护',
    'General Maintenance': '综合维修',
    'General Facility Maintenance': '综合维修与通用维护',
    'Emergency Inspection': '紧急安全巡检',
    Other: '其他',
  },

  // Urgency / Priority Levels
  urgency: {
    emergency: '紧急',
    high: '高',
    medium: '普通',
    low: '低',
  },

  // Technical Skills
  skills: {
    HVAC: '空调暖通',
    Plumbing: '水暖管道',
    Electrical: '强电电路',
    Networking: '弱电网络',
    Appliance: '家电精修',
    General: '综合检修',
    HighAltitude: '高空作业',
    Gas: '燃气安全',
  },

  // Service Branches (China localized seed mapping)
  branches: {
    GZ_TH: {
      name: '广州天河服务中心',
      code: 'GZ-TH-01',
      region: '广东省 广州市 天河区',
      coverage: '天河区、越秀区、海珠区',
    },
    SZ_NS: {
      name: '深圳南山服务中心',
      code: 'SZ-NS-01',
      region: '广东省 深圳市 南山区',
      coverage: '南山区、福田区、宝安区',
    },
    BJ_HD: {
      name: '北京海淀服务中心',
      code: 'BJ-HD-01',
      region: '北京市 海淀区',
      coverage: '海淀区、朝阳区、西城区',
    },
    SH_PD: {
      name: '上海浦东服务中心',
      code: 'SH-PD-01',
      region: '上海市 浦东新区',
      coverage: '浦东新区、黄浦区、徐汇区',
    },
  },

  // Service Teams
  teams: {
    GZ_HVAC_1: {
      name: '天河空调维修一组',
      branch: '广州天河服务中心',
      leader: '陈志强',
    },
    GZ_PLUMB_1: {
      name: '天河水暖综合组',
      branch: '广州天河服务中心',
      leader: '刘伟',
    },
    SZ_ELEC_1: {
      name: '南山电气维修一组',
      branch: '深圳南山服务中心',
      leader: '李建军',
    },
    BJ_NET_1: {
      name: '海淀弱电网络组',
      branch: '北京海淀服务中心',
      leader: '张伟',
    },
  },

  // Missing Fields in Intake Draft
  missingFields: {
    problem_description: '故障描述',
    location: '服务地址',
    preferred_time: '期望上门时间',
    service_type: '服务类型',
    urgency: '紧急程度',
  },
};
