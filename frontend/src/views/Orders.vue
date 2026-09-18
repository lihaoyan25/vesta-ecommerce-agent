<template>
  <!-- 灰金奢华渐变背景外层容器 -->
  <div class="gradient-bg min-h-screen">
    <div class="max-w-4xl mx-auto px-6 py-10">
      <h1 class="text-2xl font-semibold text-text-primary mb-8">我的订单</h1>

      <!-- 状态筛选 -->
      <div class="flex gap-3 mb-6">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          @click="switchStatus(tab.value)"
          class="px-4 py-2 rounded-full text-sm btn-transition"
          :class="currentStatus === tab.value
            ? 'bg-gradient-to-r from-yellow-500 to-amber-600 text-white'
            : 'bg-white text-text-secondary hover:text-text-primary shadow-card'"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 订单列表 -->
      <div v-if="orders.length > 0" class="space-y-4">
        <div v-for="order in orders" :key="order.order_id" class="bg-white rounded-xl shadow-card p-6">
          <!-- 订单头部 -->
          <div class="flex items-center justify-between pb-4 border-b border-border-light">
            <div class="text-sm text-text-secondary">
              <span class="mr-4">订单号：{{ order.order_no }}</span>
              <span>{{ formatDate(order.created_at) }}</span>
            </div>
            <span
              class="text-sm font-medium"
              :class="{
                'text-primary': order.status === 1,
                'text-green-600': order.status === 2,
                'text-text-tertiary': order.status === 3
              }"
            >
              {{ statusText(order) }}
            </span>
          </div>
          <!-- 商品明细 -->
          <div class="py-4 space-y-3">
            <div
              v-for="item in order.items"
              :key="item.product_id"
              class="flex items-center gap-4"
            >
              <div class="w-14 h-14 rounded-lg bg-gray-bg flex items-center justify-center flex-shrink-0 overflow-hidden">
                <img v-if="item.image_url" :src="item.image_url" alt="" class="w-full h-full object-cover" />
                <span v-else class="text-2xl">📦</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-text-primary truncate">{{ item.product_name }}</p>
                <p class="text-xs text-text-secondary mt-1">{{ formatPrice(item.product_price) }} × {{ item.quantity }}</p>
              </div>
              <p class="text-sm font-semibold text-text-primary">{{ formatPrice(item.subtotal) }}</p>
            </div>
          </div>
          <!-- 订单底部 -->
          <div class="flex items-center justify-between pt-4 border-t border-border-light">
            <div class="flex items-center gap-4 text-sm">
              <span class="text-text-primary font-semibold">
                合计：<span class="text-primary">{{ formatPrice(order.total_amount) }}</span>
              </span>
              <!-- 待支付倒计时 -->
              <span v-if="order.status === 1" class="text-text-secondary">
                {{ countdownText(order) }}
              </span>
            </div>
            <div class="flex items-center gap-3">
              <!-- 待支付：支付 + 取消 -->
              <template v-if="order.status === 1">
                <button
                  @click="handlePay(order)"
                  :disabled="paying === order.order_id"
                  class="px-5 py-2 bg-gradient-to-r from-yellow-500 to-amber-600 text-white rounded-xl text-sm btn-transition hover:from-yellow-600 hover:to-amber-700 disabled:opacity-50"
                >
                  {{ paying === order.order_id ? '支付中...' : '去支付' }}
                </button>
                <button
                  @click="handleCancel(order)"
                  class="px-4 py-2 border border-border-light rounded-xl text-sm text-text-secondary btn-transition hover:text-danger hover:border-danger"
                >
                  取消订单
                </button>
              </template>
              <!-- 已取消：删除 -->
              <button
                v-if="order.status === 3"
                @click="handleDelete(order)"
                class="px-4 py-2 border border-border-light rounded-xl text-sm text-text-secondary btn-transition hover:text-danger hover:border-danger"
              >
                删除订单
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="flex justify-center gap-2 mt-8">
        <button
          v-for="p in totalPages"
          :key="p"
          @click="switchPage(p)"
          class="w-9 h-9 rounded-lg text-sm btn-transition"
          :class="page === p
            ? 'bg-gradient-to-r from-yellow-500 to-amber-600 text-white'
            : 'bg-white text-text-secondary shadow-card hover:text-text-primary'"
        >
          {{ p }}
        </button>
      </div>

      <!-- 空状态 -->
      <EmptyState
        v-if="orders.length === 0 && !loading"
        icon="📋"
        title="暂无订单"
        description="去购物车挑选商品下单吧"
      >
        <router-link to="/" class="inline-block mt-6 px-6 py-2 bg-gradient-to-r from-yellow-500 to-amber-600 text-white rounded-full btn-transition hover:from-yellow-600 hover:to-amber-700">
          去逛逛
        </router-link>
      </EmptyState>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getOrders, payOrder, cancelOrder, deleteOrder } from '../api/order'
import { formatPrice } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'

const statusTabs = [
  { label: '全部', value: null },
  { label: '待支付', value: 1 },
  { label: '已支付', value: 2 },
  { label: '已取消', value: 3 }
]

const orders = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const currentStatus = ref(null)
const loading = ref(true)
const paying = ref(null)

// 每秒刷新一次当前时间，用于待支付倒计时
const now = ref(Date.now())
let timer = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function statusText(order) {
  return { 1: '待支付', 2: '已支付', 3: '已取消' }[order.status] || '未知'
}
function formatDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}
function countdownText(order) {
  const remainMs = new Date(order.expire_at).getTime() - now.value
  if (remainMs <= 0) return '即将取消...'
  const totalSec = Math.floor(remainMs / 1000)
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')
  return `请在 ${mm}:${ss} 内支付`
}

async function fetchOrders() {
  loading.value = true
  try {
    const res = await getOrders(page.value, pageSize.value, currentStatus.value)
    orders.value = res.items
    total.value = res.total
  } catch (e) {
    window.$toast.error(e.message)
  } finally {
    loading.value = false
  }
}

function switchStatus(value) {
  currentStatus.value = value
  page.value = 1
  fetchOrders()
}
function switchPage(p) {
  page.value = p
  fetchOrders()
}

async function handlePay(order) {
  paying.value = order.order_id
  try {
    await payOrder(order.order_id)
    window.$toast.success('支付成功')
    fetchOrders()
  } catch (e) {
    window.$toast.error(e.message)
    fetchOrders()
  } finally {
    paying.value = null
  }
}
async function handleCancel(order) {
  if (!confirm(`确定取消订单 ${order.order_no} 吗？`)) return
  try {
    await cancelOrder(order.order_id)
    window.$toast.success('订单已取消')
    fetchOrders()
  } catch (e) {
    window.$toast.error(e.message)
  }
}
async function handleDelete(order) {
  if (!confirm(`确定删除订单 ${order.order_no} 吗？删除后不可恢复`)) return
  try {
    await deleteOrder(order.order_id)
    window.$toast.success('订单已删除')
    fetchOrders()
  } catch (e) {
    window.$toast.error(e.message)
  }
}

onMounted(() => {
  fetchOrders()
  // 每秒刷新当前时间驱动倒计时; 有订单倒计时归零时重新拉取列表(后端会惰性取消)
  timer = setInterval(() => {
    now.value = Date.now()
    const expiredVisible = orders.value.some(
      o => o.status === 1 && new Date(o.expire_at).getTime() <= now.value
    )
    if (expiredVisible) fetchOrders()
  }, 1000)
})
onBeforeUnmount(() => {
  clearInterval(timer)
})
</script>
