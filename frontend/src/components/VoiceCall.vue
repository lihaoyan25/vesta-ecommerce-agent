<template>
  <!-- 顶部悬浮通话条（半透明，通话时可继续浏览商城） -->
  <div class="fixed top-0 inset-x-0 z-[70] flex justify-center px-4 pt-3 pointer-events-none">
    <div class="pointer-events-auto w-full max-w-2xl flex items-center gap-3 rounded-2xl border border-white/10 bg-black/45 backdrop-blur-md shadow-2xl px-4 py-2.5 text-white select-none">
      <!-- 状态球 -->
      <div class="relative w-9 h-9 shrink-0 flex items-center justify-center">
        <div class="absolute inset-0 rounded-full bg-gradient-to-br from-yellow-400/40 to-amber-600/25" :class="orbRingClass"></div>
        <div class="w-6 h-6 rounded-full bg-gradient-to-br from-yellow-500 to-amber-600 flex items-center justify-center">
          <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0-4a3 3 0 003-3V7a3 3 0 00-3-3 3 3 0 00-3 3v8a3 3 0 003 3z" />
          </svg>
        </div>
      </div>

      <!-- 状态 + 字幕 -->
      <div class="flex-1 min-w-0">
        <p class="text-[11px] leading-4 text-white/55 truncate">{{ errorMsg ? '通话异常' : phaseText }}</p>
        <p class="text-sm leading-5 truncate"
          :class="errorMsg ? 'text-red-400' : (liveIsUser ? 'text-white/55' : 'text-white/95')">
          {{ errorMsg || liveText || ' ' }}
        </p>
      </div>

      <!-- 挂断 -->
      <button
        @click="hangUp"
        class="shrink-0 w-9 h-9 rounded-full bg-red-500/90 hover:bg-red-500 btn-transition flex items-center justify-center"
        title="挂断"
      >
        <svg class="w-4 h-4 rotate-[135deg] text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
        </svg>
      </button>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  sessionId: { type: Number, required: true }
})
const emit = defineEmits(['close'])

const phase = ref('connecting')     // connecting / listening / thinking / speaking
const userPartial = ref('')         // ASR 实时字幕（本轮用户正在说的话）
const assistantLive = ref('')       // 当前回复文本（本轮 AI 正在说的话）
const transcript = ref([])          // 已完成轮次的对话记录 [{role:'user'|'assistant', text}]
const errorMsg = ref('')
const connected = ref(false)

let ws = null
let micStream = null
let captureCtx = null               // 16k 采集
let playCtx = null                  // 24k 播放
let workletNode = null
let micSource = null
let closedByUser = false

// 播放队列状态
let scheduledSources = []
let nextStartTime = 0
let audioDoneReceived = false

// 打断检测：客服播报期间，AEC 消除客服人声后麦克风能量持续超阈值 = 用户开口
const BARGE_IN_RMS = 0.03
const BARGE_IN_FRAMES = 2  // 连续 2 个 200ms 帧超阈值（约 400ms）即打断
let loudFrames = 0

const PHASE_TEXT = {
  connecting: '正在接通...',
  listening: '我在听，请讲',
  thinking: '客服思考中...',
  speaking: '客服正在回复'
}
const phaseText = computed(() => PHASE_TEXT[phase.value] || '')

// 顶部条单行字幕：优先显示正在进行的语音，其次最近一条对话
const liveText = computed(() => {
  if (userPartial.value) return userPartial.value
  if (assistantLive.value) return assistantLive.value
  const last = transcript.value[transcript.value.length - 1]
  return last ? last.text : ''
})
const liveIsUser = computed(() => {
  if (userPartial.value) return true
  if (assistantLive.value) return false
  const last = transcript.value[transcript.value.length - 1]
  return last ? last.role === 'user' : false
})

const orbRingClass = computed(() => {
  switch (phase.value) {
    case 'listening': return 'inset-0 animate-ping [animation-duration:2s]'
    case 'thinking': return 'inset-2 animate-pulse'
    case 'speaking': return 'inset-0 animate-ping [animation-duration:1s]'
    default: return 'inset-0 animate-pulse'
  }
})

onMounted(start)
onBeforeUnmount(cleanup)

async function start() {
  try {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前环境不支持麦克风（需 HTTPS 或 localhost 访问）')
    }
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })

    // 采集链路：16k AudioContext + AudioWorklet 输出 PCM
    captureCtx = new AudioContext({ sampleRate: 16000 })
    await captureCtx.resume()
    const workletCode = `class PCMCapture extends AudioWorkletProcessor {
      process(inputs) {
        const ch = inputs[0][0]
        if (ch) this.port.postMessage(ch.slice(0))
        return true
      }
    }
    registerProcessor('pcm-capture', PCMCapture)`
    const blob = URL.createObjectURL(new Blob([workletCode], { type: 'application/javascript' }))
    await captureCtx.audioWorklet.addModule(blob)
    workletNode = new AudioWorkletNode(captureCtx, 'pcm-capture')
    micSource = captureCtx.createMediaStreamSource(micStream)
    micSource.connect(workletNode)

    // 缓冲为 200ms（3200 采样）帧再发送
    let buffer = new Float32Array(3200)
    let offset = 0
    workletNode.port.onmessage = (e) => {
      const chunk = e.data
      let i = 0
      while (i < chunk.length) {
        const n = Math.min(chunk.length - i, 3200 - offset)
        buffer.set(chunk.subarray(i, i + n), offset)
        i += n
        offset += n
        if (offset === 3200) {
          sendPcm(buffer)
          watchBargeIn(buffer)
          buffer = new Float32Array(3200)
          offset = 0
        }
      }
    }

    // 播放链路
    playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 })
    await playCtx.resume()

    // WebSocket 通话
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const token = localStorage.getItem('token') || ''
    ws = new WebSocket(`${proto}://${location.host}/api/v1/voice/call?token=${encodeURIComponent(token)}&session=${props.sessionId}`)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => { connected.value = true }
    ws.onmessage = onWsMessage
    ws.onclose = (ev) => {
      if (closedByUser) return
      errorMsg.value = ev.code === 4503 ? '语音通话未启用' : '通话已断开'
      end()
    }
    ws.onerror = () => {}
  } catch (e) {
    errorMsg.value = e?.message || '无法启动语音通话'
    setTimeout(() => emit('close'), 2500)
  }
}

function onWsMessage(e) {
  if (e.data instanceof ArrayBuffer) {
    playChunk(e.data)
    return
  }
  let msg
  try {
    msg = JSON.parse(e.data)
  } catch {
    return
  }
  switch (msg.type) {
    case 'status':
      phase.value = msg.phase
      if (msg.phase === 'listening') {
        userPartial.value = ''
        assistantLive.value = ''
        audioDoneReceived = false
      }
      break
    case 'subtitle':
      if (phase.value === 'listening' || phase.value === 'connecting') {
        userPartial.value = msg.text
      }
      break
    case 'final':
      transcript.value.push({ role: 'user', text: msg.text })
      userPartial.value = ''
      break
    case 'assistant_delta':
      assistantLive.value += msg.text
      break
    case 'assistant_text':
      transcript.value.push({ role: 'assistant', text: msg.text })
      assistantLive.value = ''
      break
    case 'audio':
      playChunk(msg.pcm)
      break
    case 'audio_done':
      audioDoneReceived = true
      maybeNotifyAudioPlayed()
      break
    case 'interrupted':
      stopPlayback()
      assistantLive.value = ''
      break
    case 'error':
      errorMsg.value = msg.message
      break
  }
}

function sendPcm(float32) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  const pcm = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
  }
  ws.send(pcm.buffer)
}

function playChunk(b64) {
  if (!playCtx) return
  const bin = atob(b64)
  const sampleCount = bin.length >> 1
  if (sampleCount === 0) return
  const pcm = new Int16Array(sampleCount)
  for (let i = 0; i < sampleCount; i++) {
    pcm[i] = bin.charCodeAt(i * 2) | (bin.charCodeAt(i * 2 + 1) << 8)
  }
  const audioBuffer = playCtx.createBuffer(1, sampleCount, 24000)
  const channel = audioBuffer.getChannelData(0)
  for (let i = 0; i < sampleCount; i++) channel[i] = pcm[i] / 32768

  const src = playCtx.createBufferSource()
  src.buffer = audioBuffer
  src.connect(playCtx.destination)
  const startAt = Math.max(playCtx.currentTime + 0.05, nextStartTime)
  src.start(startAt)
  nextStartTime = startAt + audioBuffer.duration
  scheduledSources.push(src)
  src.onended = () => {
    scheduledSources = scheduledSources.filter(s => s !== src)
    maybeNotifyAudioPlayed()
  }
}

function maybeNotifyAudioPlayed() {
  // 后端音频全部下发且本地播放队列耗尽 → 通知后端回到聆听状态
  if (audioDoneReceived && scheduledSources.length === 0 && ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'audio_played' }))
  }
}

function stopPlayback() {
  scheduledSources.forEach(s => { try { s.stop() } catch {} })
  scheduledSources = []
  nextStartTime = 0
}

function watchBargeIn(buf) {
  // ASR 的 definite 分句要等 VAD 判停，播报期间回声残余使 VAD 无法判停，
  // 所以打断靠本地能量检测：连续多帧能量超阈值即视为用户开口。
  // 仅在本地确有音频在播时检测，避免工具执行/播报空窗期误触发
  if (phase.value !== 'speaking' || scheduledSources.length === 0) { loudFrames = 0; return }
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
  if (Math.sqrt(sum / buf.length) > BARGE_IN_RMS) {
    loudFrames += 1
    if (loudFrames >= BARGE_IN_FRAMES) {
      loudFrames = 0
      bargeIn()
    }
  } else {
    loudFrames = 0
  }
}

function bargeIn() {
  stopPlayback()
  assistantLive.value = ''
  try { ws?.send(JSON.stringify({ type: 'barge_in' })) } catch {}
}

function hangUp() {
  closedByUser = true
  try { ws?.send(JSON.stringify({ type: 'stop' })) } catch {}
  cleanup()
  emit('close')
}

function end() {
  cleanup()
  emit('close')
}

function cleanup() {
  stopPlayback()
  try { ws?.close() } catch {}
  ws = null
  try { workletNode?.disconnect() } catch {}
  try { micSource?.disconnect() } catch {}
  micStream?.getTracks().forEach(t => t.stop())
  try { captureCtx?.close() } catch {}
  try { playCtx?.close() } catch {}
  captureCtx = null
  playCtx = null
}
</script>
