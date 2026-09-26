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
      <label class="filter-item">
        <span>保养结论</span>
        <select v-model="verdictFilter">
          <option value="">全部</option>
          <option v-for="option in verdictOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>保养结论</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td :title="String(row['保养说明'] ?? '')">
            <span :class="{ 'verdict-due': row['保养结论'] === '保养到期' }">{{ row['保养结论'] ?? '—' }}</span>
          </td>
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
          <td :colspan="columns.length + 2" class="empty-state">暂无养护机械数据，可先登记养护机械</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护机械记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <header class="modal-head">
          <h3>养护机械详情</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
          <dt>保养结论</dt>
          <dd>{{ detail['保养结论'] ?? '—' }}</dd>
        </dl>
        <p class="detail-verdict">{{ detail['保养说明'] }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatItem = { label: string; value: number }

const ENDPOINT = '/api/equip'
const columns = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
const actions = ["安排保养", "确认可用", "报废机械"]
const verdictOptions = ["保养到期", "保养未到期", "日期待补", "已报废"]

const stats = ref<StatItem[]>([{"label": "在册机械", "value": 0}, {"label": "待保养机械", "value": 0}, {"label": "保养中机械", "value": 0}])
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const verdictFilter = ref('')
const detail = ref<Row | null>(null)
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  verdictFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '养护机械登记入口尚未接入审批流'
}

function closeDetail() {
  detail.value = null
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('养护机械详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('养护机械动作未生效，请稍后重试')
    }
    const result = await response.json()
    if (!result.ok) {
      throw new Error(result.message || '养护机械动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  if (verdictFilter.value) {
    query.set('verdict', verdictFilter.value)
  }
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('养护机械列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (statsResponse.ok) {
      const statsPayload = await statsResponse.json()
      stats.value = statsPayload.items ?? stats.value
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护机械列表读取失败'
  }
}

onMounted(reload)
</script>
