export interface ServiceBranch {
  id: string;
  name: string;
  code: string;
  region: string;
  address: string;
  contact: string;
  coverage: string;
}

export interface ServiceTeam {
  id: string;
  name: string;
  branchId: string;
  leader: string;
  trade?: string;
  skills: string[];
  memberTechnicianIds: number[];
}

export const branches: ServiceBranch[] = [
  {
    id: 'GZ_TH',
    name: '广州天河服务中心',
    code: 'GZ-TH-01',
    region: '广东省 广州市 天河区',
    address: '广州市天河区天河路 388 号华南维保中心',
    contact: '020-8823-1100',
    coverage: '天河区、越秀区、海珠区',
  },
  {
    id: 'SZ_NS',
    name: '深圳南山服务中心',
    code: 'SZ-NS-01',
    region: '广东省 深圳市 南山区',
    address: '深圳市南山区科技园科发路 18 号运营站',
    contact: '0755-8621-3322',
    coverage: '南山区、福田区、宝安区',
  },
  {
    id: 'BJ_HD',
    name: '北京海淀服务中心',
    code: 'BJ-HD-01',
    region: '北京市 海淀区',
    address: '北京市海淀区中关村南大街 1 号调度服务站',
    contact: '010-6278-8800',
    coverage: '海淀区、朝阳区、西城区',
  },
  {
    id: 'SH_PD',
    name: '上海浦东服务中心',
    code: 'SH-PD-01',
    region: '上海市 浦东新区',
    address: '上海市浦东新区张江高科祖冲之路 88 号',
    contact: '021-5080-9911',
    coverage: '浦东新区、黄浦区、徐汇区',
  },
];

export const teams: ServiceTeam[] = [
  {
    id: 'GZ_HVAC_1',
    name: '天河空调维修一组',
    branchId: 'GZ_TH',
    leader: '陈志强',
    trade: 'HVAC',
    skills: ['HVAC', 'Appliance'],
    memberTechnicianIds: [1, 2],
  },
  {
    id: 'GZ_PLUMB_1',
    name: '天河水暖综合组',
    branchId: 'GZ_TH',
    leader: '刘伟',
    trade: 'Plumbing',
    skills: ['Plumbing', 'General'],
    memberTechnicianIds: [3],
  },
  {
    id: 'SZ_ELEC_1',
    name: '南山电气维修一组',
    branchId: 'SZ_NS',
    leader: '李建军',
    trade: 'Electrical',
    skills: ['Electrical', 'Networking'],
    memberTechnicianIds: [4],
  },
  {
    id: 'BJ_NET_1',
    name: '海淀弱电网络组',
    branchId: 'BJ_HD',
    leader: '张伟',
    trade: 'Networking',
    skills: ['Networking', 'General'],
    memberTechnicianIds: [5],
  },
];
