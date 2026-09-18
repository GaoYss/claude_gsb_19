import http, { createResourceApi } from './client'

const base = createResourceApi('green-spaces')

export const greenSpaceApi = {
  ...base,
  /** 下拉选项：仅返回未归档绿地 */
  options: (params) => http.get('/green-spaces/options', { params }),
  districts: () => http.get('/green-spaces/districts'),
  /** 绿地档案：台账 + 养护概览 + 近期任务/记录/更换 */
  profile: (id) => http.get(`/green-spaces/${id}/profile`),
  /** 统一时间线：任务 / 养护记录 / 绿植更换按日期合并，types 为逗号分隔的类型 */
  timeline: (id, types) =>
    http.get(`/green-spaces/${id}/timeline`, { params: types?.length ? { types: types.join(',') } : {} }),
}
