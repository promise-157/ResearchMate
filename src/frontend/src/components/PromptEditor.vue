<template>
  <div class="prompt-editor">
    <div class="pe-toggle" @click="expanded = !expanded">
      <span>⚙ 自定义分析模板</span>
      <el-icon><component :is="expanded ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
    </div>
    <div v-if="expanded" class="pe-body">
      <div class="pe-preset-row">
        <el-select v-model="selectedPreset" placeholder="选择预设模板..." size="small" style="flex:1" @change="onPresetSelect">
          <el-option v-for="(p, i) in presets" :key="i" :label="p.label" :value="i" />
        </el-select>
        <el-button size="small" @click="saveCustom">💾 保存当前</el-button>
      </div>
      <el-input v-model="localPrompt" type="textarea" :rows="8" class="pe-textarea" />
      <div class="pe-info">📂 可访问: {{ dataScope }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  presets: { type: Array, default: () => [] },
  dataScope: { type: String, default: '当前工作区论文标题+关键词' },
  storageKey: { type: String, default: 'rm-prompt' },
})

const emit = defineEmits(['update:modelValue'])

const expanded = ref(false)
const selectedPreset = ref(-1)
const localPrompt = ref(props.modelValue)

watch(() => props.modelValue, (v) => { localPrompt.value = v })
watch(localPrompt, (v) => emit('update:modelValue', v))

function onPresetSelect(idx) {
  if (idx >= 0 && props.presets[idx]) {
    localPrompt.value = props.presets[idx].template
  }
}

function saveCustom() {
  const saved = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
  const label = prompt('模板名称（如：我的精简分析）:')
  if (!label) return
  saved.push({ label, template: localPrompt.value })
  localStorage.setItem(props.storageKey, JSON.stringify(saved))
  // trigger reactivity
  selectedPreset.value = -1
  ElMessage.success('已保存')
}
</script>

<script>
import { ElMessage } from 'element-plus'
</script>

<style scoped>
.prompt-editor {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-sm);
}
.pe-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 12px; cursor: pointer; user-select: none;
  font-size: var(--font-size-xs); color: var(--color-text-secondary);
}
.pe-toggle:hover { color: var(--color-primary); }
.pe-body { padding: 0 12px 12px; }
.pe-preset-row { display: flex; gap: var(--space-xs); margin-bottom: var(--space-sm); }
.pe-textarea { margin-bottom: var(--space-xs); font-size: var(--font-size-xs); }
.pe-info { font-size: 11px; color: var(--color-text-disabled); }
</style>
