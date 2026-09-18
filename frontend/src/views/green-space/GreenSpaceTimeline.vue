<template>
  <div class="timeline-panel">
    <div class="timeline-toolbar">
      <el-checkbox-group v-model="selectedTypes" size="small" @change="load">
        <el-checkbox-button v-for="item in TYPE_OPTIONS" :key="item.value" :value="item.value">
          {{ item.label }}
          <span class="type-count">{{ statistics[item.countKey] ?? 0 }}</span>
        </el-checkbox-button>
      </el-checkbox-group>
      <div class="toolbar-right">
        <el-tag v-if="statistics.long_gap_count" type="warning" effect="light" round disable-transitions>
          养护空档 {{ statistics.long_gap_count }} 处
        </el-tag>
        <el-button :icon="'Refresh'" text @click="load">刷新</el-button>
      </div>
    </div>

    <div v-if="selectedTypes.length === 0" class="timeline-empty">
      <el-empty description="请至少选择一种动态类型" :image-size="80" />
    </div>
    <el-skeleton v-else-if="loading" :rows="4" animated />
    <div v-else-if="items.length === 0" class="timeline-empty">
      <el-empty description="该绿地暂无相关动态记录" />
    </div>

    <ul v-else class="timeline">
      <li v-for="(item, index) in items" :key="`${item.type}-${item.ref_id}`" class="timeline__item">
        <div class="timeline__rail">
          <span class="timeline__dot" :class="`timeline__dot--${item.type}`">
            <el-icon><component :is="TYPE_META[item.type].icon" /></el-icon>
          </span>
          <template v-if="index < items.length - 1">
            <div class="timeline__line" :class="{ 'timeline__line--gap': item.is_long_gap }"></div>
            <span class="gap-tag" :class="{ 'gap-tag--long': item.is_long_gap }">
              {{ item.gap_days === 0 ? '同日' : `间隔 ${item.gap_days} 天` }}
            </span>
          </template>
        </div>

        <div class="timeline__card" :class="{ 'timeline__card--gap': item.is_long_gap }">
          <div class="card-header">
            <span class="card-date">{{ item.event_date }}</span>
            <el-tag size="small" effect="light" :color="TYPE_META[item.type].softColor"
                    :style="{ color: TYPE_META[item.type].color, borderColor: TYPE_META[item.type].borderColor }">
              {{ item.type_label }}
            </el-tag>
            <el-tag v-if="item.is_overdue" size="small" type="danger" effect="plain">逾期</el-tag>
            <el-tag size="small" :type="statusTagType(item)" effect="plain">{{ item.status_label }}</el-tag>
            <span class="card-no">{{ item.no }}</span>
          </div>

          <div class="card-body">
            <el-button
              v-if="item.type === 'task' || item.type === 'record'"
              link type="primary" class="card-title-button" @click="openDetail(item)"
            >{{ item.title }}</el-button>
            <span v-else class="card-title">{{ item.title }}</span>
            <el-tag v-if="item.category_label" size="small" type="info" effect="plain" class="card-category">
              {{ item.category_label }}
            </el-tag>
          </div>

          <div class="card-meta">
            <template v-if="item.type === 'task'">
              <span><el-icon><User /></el-icon>{{ item.executor || '未指派班组' }}</span>
            </template>
            <template v-else-if="item.type === 'record'">
              <span><el-icon><User /></el-icon>{{ item.worker || '作业人员未填' }}</span>
              <span><el-icon><Timer /></el-icon>{{ formatNumber(item.work_hours) }} h</span>
            </template>
            <template v-else>
              <span><el-icon><Cherry /></el-icon>{{ formatNumber(item.quantity) }} {{ item.unit_label }}</span>
              <span><el-icon><Money /></el-icon>{{ formatCurrency(item.amount) }}</span>
              <span v-if="item.executor"><el-icon><User /></el-icon>{{ item.executor }}</span>
              <el-button link type="primary" size="small" @click="replacementDialog.open(item)">查看 / 编辑</el-button>
            </template>
          </div>
        </div>
      </li>
    </ul>

    <TaskDetailDrawer ref="taskDrawer" @updated="emitChanged" />
    <RecordDetailDialog ref="recordDialog" />
    <ReplacementFormDialog ref="replacementDialog" @saved="emitChanged" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { greenSpaceApi } from '@/api'
import { formatCurrency, formatNumber } from '@/utils/format'
import RecordDetailDialog from '@/views/record/RecordDetailDialog.vue'
import ReplacementFormDialog from '@/views/replacement/ReplacementFormDialog.vue'
import TaskDetailDrawer from '@/views/task/TaskDetailDrawer.vue'

const props = defineProps({
  spaceId: { type: [Number, String], required: true },
})
const emit = defineEmits(['changed'])

const TYPE_OPTIONS = [
  { value: 'task', label: '养护任务', countKey: 'task_count' },
  { value: 'record', label: '养护记录', countKey: 'record_count' },
  { value: 'replacement', label: '绿植更换', countKey: 'replacement_count' },
]

const TYPE_META = {
  task: { icon: 'Tickets', color: '#2f855a', softColor: '#e2f0e9', borderColor: '#a9d4bd' },
  record: { icon: 'Notebook', color: '#3375b8', softColor: '#e7f0fa', borderColor: '#b4cfee' },
  replacement: { icon: 'Cherry', color: '#b5720c', softColor: '#fbf1df', borderColor: '#ecd2a1' },
}

const QUALITY_TAG = { qualified: 'success', unqualified: 'danger', pending: 'warning' }

const selectedTypes = ref(['task', 'record', 'replacement'])
const items = ref([])
const statistics = ref({})
const loading = ref(false)

const taskDrawer = ref(null)
const recordDialog = ref(null)
const replacementDialog = ref(null)

async function load() {
  if (!props.spaceId) {
    items.value = []
    return
  }
  if (selectedTypes.value.length === 0) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const data = await greenSpaceApi.timeline(props.spaceId, selectedTypes.value)
    items.value = data.items || []
    statistics.value = data.statistics || {}
  } finally {
    loading.value = false
  }
}

function statusTagType(item) {
  if (item.type === 'record') return QUALITY_TAG[item.status] || 'info'
  if (item.type === 'task') {
    return { completed: 'success', in_progress: 'warning', pending: 'info', cancelled: 'danger' }[item.status]
  }
  return 'info'
}

function openDetail(item) {
  if (item.type === 'task') taskDrawer.value.open(item.ref_id)
  else if (item.type === 'record') recordDialog.value.open(item.ref_id)
}

function emitChanged() {
  load()
  emit('changed')
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped>
.timeline-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.timeline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.type-count {
  margin-left: 4px;
  color: #909399;
  font-size: 12px;
}

.timeline-empty {
  padding: 24px 0;
}

.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}

.timeline__item {
  display: flex;
  align-items: stretch;
}

.timeline__rail {
  position: relative;
  width: 36px;
  flex: 0 0 36px;
  display: flex;
  justify-content: center;
}

.timeline__dot {
  z-index: 1;
  width: 30px;
  height: 30px;
  margin-top: 14px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 15px;
  box-shadow: 0 0 0 3px #fff;
}

.timeline__dot--task {
  background: #2f855a;
}

.timeline__dot--record {
  background: #3375b8;
}

.timeline__dot--replacement {
  background: #d4880f;
}

.timeline__line {
  position: absolute;
  top: 46px;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  background: #dfe6e1;
}

.timeline__line--gap {
  width: 0;
  border-left: 2px dashed #e6a23c;
  background: transparent;
}

.gap-tag {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 1;
  transform: translate(-50%, -50%);
  padding: 1px 8px;
  border-radius: 10px;
  background: #f1f4f2;
  border: 1px solid #e0e6e2;
  color: #909399;
  font-size: 11px;
  line-height: 18px;
  white-space: nowrap;
}

.gap-tag--long {
  background: #fdf0e6;
  border-color: #f0b87d;
  color: #b26a16;
  font-weight: 600;
}

.timeline__card {
  flex: 1;
  min-width: 0;
  margin: 6px 0 12px 8px;
  padding: 10px 14px;
  border: 1px solid var(--gs-border);
  border-left: 3px solid #c9d6cf;
  border-radius: 6px;
  background: #fcfdfc;
  transition: box-shadow 0.15s ease;
}

.timeline__card:hover {
  box-shadow: 0 2px 10px rgba(47, 133, 90, 0.08);
}

.timeline__card--gap {
  border-left-color: #e6a23c;
  background: #fffdf8;
}

.card-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.card-date {
  font-weight: 600;
  color: #303133;
}

.card-no {
  margin-left: auto;
  color: #a8abb2;
  font-size: 12px;
}

.card-body {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.card-title {
  color: #303133;
  font-size: 14px;
  word-break: break-all;
}

.card-title-button {
  font-size: 14px;
  height: auto;
  padding: 0;
  text-align: left;
  white-space: normal;
}

.card-title-button :deep(span) {
  white-space: normal;
  word-break: break-all;
}

.card-category {
  flex: 0 0 auto;
}

.card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.card-meta .el-icon {
  color: #a8abb2;
}
</style>
