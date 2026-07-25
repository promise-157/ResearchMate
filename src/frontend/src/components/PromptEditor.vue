<template>
  <div class="prompt-editor">
    <div class="pe-top">
      <el-select v-model="activePreset" placeholder="选择预设模板..." size="small" style="flex:1" @change="onPresetSelect" clearable>
        <el-option v-for="(p, i) in presets" :key="i" :label="p.label" :value="i" />
        <el-option label="自定义保存的模板..." value="__custom__" />
      </el-select>
      <el-tag v-if="activeLabel" size="small" type="primary" effect="plain">{{ activeLabel }}</el-tag>
      <el-button size="small" :icon="saved ? 'Check' : ''" @click="saveCustom">{{ saved ? '已保存' : '💾' }}</el-button>
    </div>
    <el-input
      v-model="localPrompt"
      type="textarea"
      :rows="6"
      placeholder="输入自定义指令（选填），将拼接在模板后面发给 AI。模板需包含「返回JSON格式」指令。"
      class="pe-textarea"
    />
    <div class="pe-bottom">
      <span class="pe-info">📂 可访问: {{ dataScope }}</span>
      <span class="pe-info" style="color:var(--color-warning)">⚠ AI需要「返回JSON格式」指令</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: String, default: '' },
  presets: { type: Array, default: () => [] },
  dataScope: { type: String, default: '当前工作区论文标题+关键词' },
  storageKey: { type: String, default: 'rm-prompt' },
})

const emit = defineEmits(['update:modelValue'])

const localPrompt = ref(props.modelValue)
const activePreset = ref(-1)
const activeLabel = ref('')
const saved = ref(false)

watch(() => props.modelValue, (v) => { localPrompt.value = v })
watch(localPrompt, (v) => emit('update:modelValue', v))

function onPresetSelect(idx) {
  if (idx === '__custom__') {
    // 加载自定义保存的模板列表
    const savedList = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
    if (savedList.length === 0) {
      ElMessage.info('暂无保存的模板，请先在输入框写模板再点💾保存')
      activePreset.value = -1
      return
    }
    // 简化：加载最近保存的
    const last = savedList[savedList.length - 1]
    localPrompt.value = last.template
    activeLabel.value = '自定义: ' + last.label
    return
  }
  if (idx >= 0 && props.presets[idx]) {
    localPrompt.value = props.presets[idx].template
    activeLabel.value = props.presets[idx].label
    saved.value = false
  }
}

function saveCustom() {
  if (!localPrompt.value.trim()) return
  const savedList = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
  const label = prompt('模板名称（如：我的精简分析）:')
  if (!label) return
  savedList.push({ label, template: localPrompt.value })
  localStorage.setItem(props.storageKey, JSON.stringify(savedList))
  activeLabel.value = '自定义: ' + label
  saved.value = true
  ElMessage.success('已保存「' + label + '」')
}
</script>

<style scoped>
.prompt-editor {
  margin-bottom: var(--space-sm);
}
.pe-top {
  display: flex; gap: var(--space-xs); align-items: center;
  margin-bottom: var(--space-xs);
}
.pe-textarea { font-size: var(--font-size-xs); }
.pe-bottom {
  display: flex; justify-content: space-between;
  margin-top: var(--space-xs);
}
.pe-info { font-size: 11px; color: var(--color-text-disabled); }
</style>
