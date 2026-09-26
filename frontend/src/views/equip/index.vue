<template>
  <section class="page" data-module="equip">
    <header class="page-head">
      <div>
        <h2>养护机械管理</h2>
        <p class="page-desc">维护养护机械，围绕机械编号、机械名称、机械型号、停放场地做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记养护机械</button>
        <button class="btn" type="button" @click="exportRows">导出养护机械清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无养护机械数据，可先登记养护机械</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护机械记录</span>
      <span v-if="noticeMessage" class="info-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <h3>养护机械详情</h3>
        <dl class="detail-list">
          <template v-for="field in detailFields" :key="field.key">
            <dt>{{ field.label }}</dt>
            <dd>{{ detail[field.key] ?? '—' }}</dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记养护机械</h3>
        <label v-for="field in createFields" :key="field.name" class="form-item">
          <span>{{ field.label }}<em v-if="field.required">（必填）</em></span>
          <input v-model="createForm[field.name]" :type="field.type ?? 'text'" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="submit">提交登记</button>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/equip'
const columns = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态", "保养结论"]
const actions = ["安排保养", "确认可用", "报废机械"]
const detailFields = [...columns.map((label) => ({ label, key: label })), { label: '当前状态', key: 'status' }]
const createFields = [
  { name: '机械编号', label: '机械编号', required: true },
  { name: '机械名称', label: '机械名称', required: true },
  { name: '机械型号', label: '机械型号', required: true },
  { name: '停放场地', label: '停放场地' },
  { name: '上次保养日', label: '上次保养日', type: 'date' },
  { name: '下次保养日', label: '下次保养日', type: 'date' },
  { name: '责任人', label: '责任人' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([{"label": "在册机械", "value": 0}, {"label": "待保养机械", "value": 0}, {"label": "保养中机械", "value": 0}])
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const detail = ref<Row | null>(null)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

function closeDetail() {
  detail.value = null
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detail.value = await fetchJson<Row>(`${ENDPOINT}/${row.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械详情读取失败'
  }
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '养护机械登记失败，请稍后重试')
    }
    noticeMessage.value = payload.message ?? '养护机械已登记'
    closeCreate()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '养护机械动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('养护机械列表读取失败')
    }
    if (!statsResponse.ok) {
      throw new Error('养护机械统计读取失败')
    }
    const listPayload = await listResponse.json()
    const statsPayload = await statsResponse.json()
    rows.value = listPayload.items ?? []
    total.value = listPayload.total ?? rows.value.length
    stats.value = statsPayload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.info-text { color: var(--brand); }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal-card { background: #fff; border-radius: 8px; padding: 16px 20px; width: 420px; max-width: 90vw; max-height: 80vh; overflow: auto; }
.detail-list { display: grid; grid-template-columns: 96px 1fr; gap: 6px 12px; margin: 0 0 12px; }
.detail-list dt { color: var(--muted); font-size: 13px; }
.detail-list dd { margin: 0; font-size: 13px; }
.form-item { display: block; margin-bottom: 10px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; }
.form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
</style>
