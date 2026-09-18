<template>
  <div class="space-timeline" v-loading="loading">
    <div class="timeline-toolbar">
      <el-radio-group v-model="activeType" size="small">
        <el-radio-button v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">
          {{ opt.label }}
          <span class="type-count">{{ countOf(opt.value) }}</span>
        </el-radio-button>
      </el-radio-group>
      <span class="timeline-hint">
        共 <strong>{{ events.length }}</strong> 条
        <template v-if="longGapCount">
          ，检出 <span class="long-gap-text">{{ longGapCount }} 段超过 {{ LONG_GAP_DAYS }} 天的养护空档</span>
        </template>
      </span>
    </div>

    <el-empty v-if="!loading && !events.length" description="该类型暂无记录" :image-size="80" />

    <div v-else class="timeline">
      <div v-for="(item, index) in events" :key="`${item.type}-${item.id}`" class="tl-item">
        <div class="tl-rail">
          <div class="tl-node" :style="{ backgroundColor: typeMeta[item.type].color }"
               :title="item.type_label">
            <el-icon :size="14"><component :is="typeMeta[item.type].icon" /></el-icon>
          </div>
          <div v-if="index < events.length - 1"
               class="tl-connector" :class="{ 'tl-connector--long': item.is_long_gap }">
            <span class="tl-gap" :class="{ 'tl-gap--long': item.is_long_gap }">
              <el-icon v-if="item.is_long_gap" :size="11"><WarningFilled /></el-icon>
              间隔 {{ item.gap_days }} 天
            </span>
          </div>
        </div>

        <div class="tl-card" :class="{ 'tl-card--clickable': item.type !== 'replacement' }"
             @click="openDetail(item)">
          <div class="tl-card__header">
            <span class="tl-card__title">{{ item.event_title }}</span>
            <span class="tl-card__date">{{ item.event_date }}</span>
          </div>

          <div class="tl-card__tags">
            <el-tag size="small" effect="plain" :color="`${typeMeta[item.type].color}14`"
                    :style="{ color: typeMeta[item.type].color, borderColor: `${typeMeta[item.type].color}55` }">
              {{ item.type_label }}
            </el-tag>

            <template v-if="item.type === 'task'">
              <EnumTag group="task_type" :value="item.task_type" :label="item.task_type_label" />
              <EnumTag group="task_priority" :value="item.priority" :label="item.priority_label" />
              <EnumTag group="task_status" :value="item.status" :label="item.status_label" />
              <el-tag v-if="item.is_overdue" type="danger" size="small" effect="plain">逾期</el-tag>
            </template>
            <template v-else-if="item.type === 'record'">
              <EnumTag group="quality_result" :value="item.quality_result" :label="item.quality_result_label" />
              <el-tag v-if="item.weather_label" size="small" type="info" effect="plain">{{ item.weather_label }}</el-tag>
            </template>
            <template v-else>
              <EnumTag group="plant_category" :value="item.plant_category" :label="item.plant_category_label" />
              <EnumTag group="replacement_reason" :value="item.reason" :label="item.reason_label" />
            </template>
          </div>

          <div class="tl-card__meta">
            <template v-if="item.type === 'task'">
              <span>执行班组：{{ item.executor || '未指派' }}</span>
              <span v-if="item.completed_at">完成于 {{ formatDateTime(item.completed_at) }}</span>
            </template>
            <template v-else-if="item.type === 'record'">
              <span>作业人员：{{ item.worker || '-' }}</span>
              <span>工时：{{ formatHours(item.work_hours) }}</span>
            </template>
            <template v-else>
              <span>规格：{{ item.spec || '-' }}</span>
              <span>数量：{{ formatNumber(item.quantity) }} {{ item.unit_label }}</span>
              <span>金额：{{ formatCurrency(item.amount) }}</span>
            </template>
          </div>
        </div>
      </div>
    </div>

    <TaskDetailDrawer ref="taskDrawer" @updated="onTaskUpdated" />
    <RecordDetailDialog ref="recordDialog" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { greenSpaceApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import { formatCurrency, formatDateTime, formatHours, formatNumber } from '@/utils/format'

import RecordDetailDialog from '../record/RecordDetailDialog.vue'
import TaskDetailDrawer from '../task/TaskDetailDrawer.vue'

const props = defineProps({
  spaceId: { type: [Number, String], required: true },
  /** 档案接口下发的全量时间线，切换到「全部」时直接复用，避免重复请求 */
  initialEvents: { type: Array, default: () => [] },
})

const emit = defineEmits(['changed'])

const LONG_GAP_DAYS = 30

const TYPE_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'task', label: '养护任务' },
  { value: 'record', label: '养护记录' },
  { value: 'replacement', label: '绿植更换' },
]

const typeMeta = {
  task: { label: '养护任务', icon: 'Tickets', color: '#409eff' },
  record: { label: '养护记录', icon: 'Notebook', color: '#2f855a' },
  replacement: { label: '绿植更换', icon: 'Cherry', color: '#e6a23c' },
}

const router = useRouter()
const activeType = ref('all')
const events = ref(props.initialEvents)
const loading = ref(false)
const taskDrawer = ref(null)
const recordDialog = ref(null)

const longGapCount = computed(() => events.value.filter((item) => item.is_long_gap).length)

function countOf(type) {
  if (type === 'all') return props.initialEvents.length
  return props.initialEvents.filter((item) => item.type === type).length
}

watch(activeType, (type) => {
  if (type === 'all') {
    events.value = props.initialEvents
    return
  }
  fetchFiltered(type)
})

watch(
  () => props.initialEvents,
  (items) => {
    if (activeType.value === 'all') events.value = items
  },
)

async function fetchFiltered(type) {
  loading.value = true
  try {
    const data = await greenSpaceApi.timeline(props.spaceId, { types: type })
    events.value = data.items || []
  } finally {
    loading.value = false
  }
}

function onTaskUpdated() {
  // 父级重新拉 profile 刷新计数；若当前在筛选视图，同时刷新该类型时间线
  emit('changed')
  if (activeType.value !== 'all') fetchFiltered(activeType.value)
}

function openDetail(item) {
  if (item.type === 'task') {
    taskDrawer.value.open(item.id)
  } else if (item.type === 'record') {
    recordDialog.value.open(item.id)
  } else {
    router.push({ name: 'replacement-list', query: { green_space_id: props.spaceId } })
  }
}
</script>

<style scoped>
.timeline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.type-count {
  color: #909399;
  font-size: 12px;
  margin-left: 2px;
}

.timeline-hint {
  color: #909399;
  font-size: 13px;
}

.timeline-hint strong {
  color: var(--gs-primary);
}

.long-gap-text {
  color: #e6a23c;
  font-weight: 600;
}

.timeline {
  padding-top: 4px;
}

.tl-item {
  display: flex;
  align-items: stretch;
}

.tl-rail {
  width: 40px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tl-node {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 3px #fff;
  z-index: 1;
  flex-shrink: 0;
}

.tl-connector {
  flex: 1;
  width: 2px;
  min-height: 34px;
  background: var(--gs-border);
  position: relative;
  margin: 2px 0;
}

.tl-connector--long {
  background: repeating-linear-gradient(
    to bottom,
    #e6a23c 0,
    #e6a23c 5px,
    transparent 5px,
    transparent 10px
  );
  width: 3px;
}

.tl-gap {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #f4f7f5;
  border: 1px solid var(--gs-border);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  line-height: 1.6;
}

.tl-gap--long {
  background: #fdf6ec;
  border-color: #f5dab1;
  color: #b88230;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.tl-card {
  flex: 1;
  background: #fff;
  border: 1px solid var(--gs-border);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 0 0 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tl-card--clickable {
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.tl-card--clickable:hover {
  border-color: var(--gs-primary-light);
  box-shadow: 0 2px 10px rgba(47, 133, 90, 0.12);
}

.tl-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tl-card__title {
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tl-card__date {
  color: #909399;
  font-size: 13px;
  flex-shrink: 0;
}

.tl-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tl-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: #606266;
  font-size: 13px;
}
</style>
