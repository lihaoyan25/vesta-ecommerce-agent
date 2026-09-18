<template>
  <!-- 悬浮球 -->
  <button
    v-if="!chatStore.open"
    @click="openWidget"
    aria-label="智能客服"
    class="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-yellow-500 to-amber-600 text-white shadow-lg flex items-center justify-center btn-transition hover:scale-105"
  >
    <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0-4a3 3 0 003-3V7a3 3 0 00-3-3 3 3 0 00-3 3v8a3 3 0 003 3z" />
    </svg>
  </button>

  <!-- 对话面板 -->
  <transition name="chat-slide">
    <div
      v-if="chatStore.open"
      class="fixed bottom-6 right-6 z-50 w-[400px] max-w-[92vw] h-[640px] max-h-[78vh] bg-white/85 backdrop-blur-xl border border-border-light rounded-2xl shadow-2xl flex flex-col overflow-hidden"
    >
      <!-- 头部 -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-border-light bg-white/60">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full bg-green-500"></span>
          <span class="font-medium text-text-primary text-sm">VESTA 智能客服</span>
        </div>
        <div class="flex items-center gap-1">
          <button
            @click="startVoiceCall"
            title="语音通话"
            class="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-gray-bg btn-transition"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
          </button>
          <button
            @click="view = view === 'chat' ? 'sessions' : 'chat'"
            :title="view === 'chat' ? '历史会话' : '返回对话'"
            class="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-gray-bg btn-transition"
          >
            <svg v-if="view === 'chat'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
          <button
            @click="handleNewSession"
            title="新对话"
            class="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:text-primary hover:bg-gray-bg btn-transition"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            @click="chatStore.open = false"
            title="收起"
            class="w-8 h-8 rounded-lg flex items-center justify-center text-text-secondary hover:text-text-primary hover:bg-gray-bg btn-transition"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- 会话列表视图 -->
      <div v-if="view === 'sessions'" class="flex-1 overflow-y-auto p-3 space-y-2">
        <div
          v-for="s in chatStore.sessions"
          :key="s.session_id"
          @click="handleSwitchSession(s.session_id)"
          class="px-3 py-2.5 rounded-xl cursor-pointer btn-transition flex items-center justify-between gap-2"
          :class="s.session_id === chatStore.currentSessionId ? 'bg-amber-50 border border-amber-200' : 'bg-white hover:bg-gray-bg border border-transparent'"
        >
          <div class="min-w-0">
            <p class="text-sm text-text-primary truncate">{{ s.title }}</p>
            <p class="text-xs text-text-tertiary mt-0.5">{{ formatTime(s.updated_at) }}</p>
          </div>
          <button
            @click.stop="handleDeleteSession(s)"
            class="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-text-tertiary hover:text-danger hover:bg-red-50 btn-transition"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
        <p v-if="chatStore.sessions.length === 0" class="text-center text-sm text-text-tertiary py-8">
          暂无历史会话
        </p>
      </div>

      <!-- 对话视图 -->
      <template v-else>
        <!-- 消息区 -->
        <div ref="messagesRef" class="flex-1 overflow-y-auto p-4 space-y-3">
          <!-- 空会话: 招呼语 + 预设问题卡片 -->
          <template v-if="chatStore.isEmpty">
            <div class="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-tl-sm bg-white border border-border-light text-sm text-text-primary whitespace-pre-wrap shadow-card">
              {{ WELCOME_TEXT }}
            </div>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-for="q in PRESET_QUESTIONS"
                :key="q"
                @click="inputText = q"
                class="px-3 py-1.5 rounded-full bg-white border border-border-light text-xs text-text-secondary btn-transition hover:text-primary hover:border-primary shadow-card"
              >
                {{ q }}
              </button>
            </div>
          </template>

          <!-- 消息气泡 -->
          <template v-for="(m, i) in chatStore.messages" :key="i">
            <!-- 用户消息 -->
            <div v-if="m.role === 'user'" class="flex justify-end">
              <div class="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-gradient-to-r from-yellow-500 to-amber-600 text-white text-sm whitespace-pre-wrap shadow-card">
                <div
                  v-if="m.context"
                  class="mb-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/20 text-xs"
                >
                  {{ m.context.type === 'product' ? '商品' : '订单' }}卡片
                </div>
                <div>{{ m.content }}</div>
              </div>
            </div>
            <!-- 客服消息 -->
            <div v-else class="flex justify-start">
              <div class="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-tl-sm bg-white border border-border-light text-sm text-text-primary shadow-card">
                <div v-if="m.streaming && m.toolStatus" class="flex items-center gap-1.5 text-xs text-primary mb-1.5">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                  {{ m.toolStatus }}...
                </div>
                <!-- 等待首字回复: 跳动圆点 + 柔闪提示文字 -->
                <div v-if="m.streaming && !m.content && !m.toolStatus" class="flex items-center gap-2 py-0.5">
                  <span class="typing-dots"><i></i><i></i><i></i></span>
                  <span class="text-xs text-text-tertiary blink-soft">客服正在赶来...请稍等</span>
                </div>
                <!-- markdown 渲染(流式期间每次增量都会重渲染) -->
                <div v-if="m.content" class="md-content break-words" v-html="renderMarkdown(m.content)"></div>
                <span v-if="m.streaming && m.content && !m.toolStatus" class="text-primary animate-pulse">▍</span>
              </div>
            </div>
          </template>
        </div>

        <!-- 推荐卡片: 仅空会话(新对话)时出现一次, 可手动关闭 -->
        <div v-if="chatStore.isEmpty && !cardsDismissed && allCards.length > 0" class="border-t border-border-light bg-white/50 px-3 py-2">
          <div class="flex items-center justify-between mb-1.5">
            <p class="text-xs text-text-tertiary">猜你想问</p>
            <button
              @click="cardsDismissed = true"
              title="关闭推荐"
              class="w-5 h-5 flex items-center justify-center rounded text-text-tertiary hover:text-text-primary hover:bg-gray-bg btn-transition"
            >
              ✕
            </button>
          </div>
          <div class="flex gap-2 overflow-x-auto pb-1">
            <div
              v-for="card in allCards"
              :key="card.key"
              class="flex-shrink-0 w-44 bg-white rounded-xl border border-border-light p-2.5 shadow-card"
            >
              <div class="flex items-center gap-1.5 mb-1">
                <span class="px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-primary">{{ card.badge }}</span>
                <span v-if="card.sub" class="text-[10px] text-text-tertiary truncate">{{ card.sub }}</span>
              </div>
              <p class="text-xs text-text-primary truncate mb-2">{{ card.title }}</p>
              <button
                @click="addCard(card)"
                class="text-xs text-primary hover:underline btn-transition font-medium"
              >
                添加
              </button>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="border-t border-border-light bg-white/70 p-3">
          <!-- 卡片预览(可移除) -->
          <div v-if="pendingContext" class="flex items-center justify-between gap-2 mb-2 px-2.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200">
            <span class="text-xs text-text-primary truncate">{{ pendingContext.label }}</span>
            <button @click="pendingContext = null" class="flex-shrink-0 w-5 h-5 flex items-center justify-center text-text-tertiary hover:text-danger btn-transition">✕</button>
          </div>
          <div class="flex items-end gap-2">
            <textarea
              v-model="inputText"
              rows="2"
              placeholder="输入您的问题, Enter 发送, Shift+Enter 换行"
              class="flex-1 px-3 py-2 rounded-xl border border-border-light text-sm bg-white input-focus resize-none"
              @keydown.enter.exact.prevent="handleSend"
            ></textarea>
            <button
              @click="handleSend"
              :disabled="chatStore.sending || !inputText.trim()"
              class="px-4 py-2 rounded-xl bg-gradient-to-r from-yellow-500 to-amber-600 text-white text-sm btn-transition hover:from-yellow-600 hover:to-amber-700 disabled:opacity-50"
            >
              {{ chatStore.sending ? '...' : '发送' }}
            </button>
          </div>
        </div>
      </template>
    </div>
  </transition>

  <!-- 语音通话全屏遮罩 -->
  <VoiceCall v-if="voiceCallOpen" :session-id="chatStore.currentSessionId" @close="voiceCallOpen = false" />
</template>
<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore } from '../stores/chat'
import { useCartStore } from '../stores/cart'
import VoiceCall from './VoiceCall.vue'

// markdown 渲染配置: GFM 表格/列表 + 单换行转 <br>, 输出经 DOMPurify 消毒防 XSS
marked.setOptions({ gfm: true, breaks: true })

function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}

const chatStore = useChatStore()
const cartStore = useCartStore()

const view = ref('chat')           // chat=对话视图, sessions=会话列表
const inputText = ref('')
const pendingContext = ref(null)   // 待发送的卡片上下文 {type, id, label}
const messagesRef = ref(null)
const voiceCallOpen = ref(false)   // 语音通话遮罩

function startVoiceCall() {
  if (!chatStore.currentSessionId) {
    window.$toast.error('会话尚未就绪, 请稍后再试')
    return
  }
  voiceCallOpen.value = true
}

const WELCOME_TEXT = '您好！我是 VESTA 智能客服, 可以帮您查询订单状态、搜索商品与库存、查看或修改购物车, 也能为您推荐商品。点击下方问题卡片或直接输入您的问题, 我来为您服务。'
const PRESET_QUESTIONS = [
  '帮我查一下我的订单状态',
  '购物车里的商品还有库存吗？',
  '推荐几款高性价比的商品',
  '如何修改我的账户密码？'
]
const ORDER_STATUS_TEXT = { 1: '待支付', 2: '已支付', 3: '已取消' }

// 推荐卡片拍平: 仅取 1 个最近订单 + 1 个在售商品(防御式取值, 后端字段缺失时不至于渲染崩溃)
const allCards = computed(() => {
  const r = chatStore.recommendations || {}
  return [
    ...(r.orders || []).slice(0, 1).map(o => ({
      key: `order-${o.id}`, type: 'order', id: o.id, badge: '订单',
      title: `订单 ${o.order_no.slice(-8)}`,
      sub: `¥${o.total_amount} · ${ORDER_STATUS_TEXT[o.status] || ''}`
    })),
    ...(r.products || []).slice(0, 1).map(p => ({
      key: `product-${p.id}`, type: 'product', id: p.id, badge: '商品',
      title: p.name, sub: `¥${p.price}`
    }))
  ]
})

// 推荐卡片关闭状态: 单次对话只出现一次, 新对话(会话变空)时重置
const cardsDismissed = ref(false)
watch(() => chatStore.isEmpty, empty => {
  if (empty) cardsDismissed.value = false
})

// 消息变化(含流式增量)时自动滚到底部
watch(
  () => chatStore.messages.map(m => m.content).join('').length + chatStore.messages.length,
  scrollBottom
)

function scrollBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function formatTime(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function openWidget() {
  chatStore.open = true
  try {
    await chatStore.ensureInit()
  } catch (e) {
    window.$toast.error(e?.message || '客服初始化失败, 请稍后再试')
  }
  // 每次展开都刷新推荐卡片(订单/购物车可能已变化), 失败仅记录不阻断对话
  chatStore.loadRecommendations().catch(e => {
    console.error('[客服] 推荐卡片加载失败:', e)
  })
  scrollBottom()
}

function addCard(card) {
  // 购物车卡片: 填充提问文本; 订单/商品卡片: 进入待发送上下文预览
  if (card.type === 'cart') {
    inputText.value = `我想咨询购物车里的「${card.title}」(数量 ${card.sub?.replace('×', '') || 1})`
    return
  }
  pendingContext.value = {
    type: card.type,
    id: card.id,
    label: `${card.badge}: ${card.title}`
  }
}

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || chatStore.sending) return
  const context = pendingContext.value
    ? { type: pendingContext.value.type, id: pendingContext.value.id }
    : null
  pendingContext.value = null
  inputText.value = ''
  try {
    await chatStore.send(content, context)
  } catch (e) {
    window.$toast.error(e?.message || '发送失败, 请稍后再试')
  } finally {
    scrollBottom()
  }
}

async function handleNewSession() {
  try {
    await chatStore.newSession()
    view.value = 'chat'
    inputText.value = ''
    pendingContext.value = null
  } catch (e) {
    window.$toast.error(e?.message || '新建会话失败')
  }
}

async function handleSwitchSession(sessionId) {
  try {
    await chatStore.switchSession(sessionId)
    view.value = 'chat'
    pendingContext.value = null
    scrollBottom()
  } catch (e) {
    window.$toast.error(e?.message || '切换会话失败')
  }
}

async function handleDeleteSession(session) {
  if (!confirm(`确定删除会话「${session.title}」吗？`)) return
  try {
    await chatStore.removeSession(session.session_id)
    window.$toast.success('会话已删除')
  } catch (e) {
    window.$toast.error(e?.message || '删除会话失败')
  }
}
</script>

<style scoped>
/* 客服气泡内 markdown 元素样式 */
.md-content :deep(p) {
  margin: 0.25rem 0;
}
.md-content :deep(p:first-child) {
  margin-top: 0;
}
.md-content :deep(p:last-child) {
  margin-bottom: 0;
}
.md-content :deep(ul),
.md-content :deep(ol) {
  margin: 0.35rem 0;
  padding-left: 1.25rem;
}
.md-content :deep(ul) {
  list-style: disc;
}
.md-content :deep(ol) {
  list-style: decimal;
}
.md-content :deep(li) {
  margin: 0.15rem 0;
}
.md-content :deep(strong) {
  font-weight: 600;
}
.md-content :deep(code) {
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem;
  background: #f3f4f6;
  font-size: 0.8em;
}
.md-content :deep(a) {
  color: var(--color-primary, #b45309);
  text-decoration: underline;
}

/* 等待回复: 三个跳动圆点 */
.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.typing-dots i {
  width: 5px;
  height: 5px;
  border-radius: 9999px;
  background: #d97706;
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.typing-dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.typing-dots i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes dot-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

/* 提示文字柔闪 */
.blink-soft {
  animation: soft-blink 1.6s infinite;
}
@keyframes soft-blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}
</style>
