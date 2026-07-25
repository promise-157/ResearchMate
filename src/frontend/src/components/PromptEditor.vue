<template>
  <div class="prompt-editor">
    <div class="pe-top">
      <el-select v-model="activePreset" placeholder="模板参考..." size="small" style="flex:1" @change="onPresetSelect" clearable>
        <el-option v-for="(p, i) in presets" :key="i" :label="p.label" :value="i" />
        <el-option label="我保存的模板..." value="__custom__" />
      </el-select>
      <el-tag v-if="activeLabel" size="small" type="primary" effect="plain">{{ activeLabel }}</el-tag>
      <el-button size="small" @click="saveCustom">💾</el-button>
    </div>
    <el-input
      v-model="localPrompt"
      type="textarea"
      :rows="6"
      placeholder="输入你的指令（选填），例如：只关注多模态方向、用英文输出、列出前5篇。留空使用默认分析。"
      class="pe-textarea"
    />
    <div class="pe-bottom">
      <span class="pe-info">📂 可访问: {{ dataScope }}</span>
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
const activePreset = ref()
const activeLabel = ref('')

watch(() => props.modelValue, (v) => { localPrompt.value = v })
watch(localPrompt, (v) => emit('update:modelValue', v))

function onPresetSelect(idx) {
  if (idx === undefined || idx === null) {
    activeLabel.value = ''
    return
  }
  if (idx === '__custom__') {
    const savedList = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
    if (savedList.length === 0) {
      ElMessage.info('暂无保存的模板，写指令后点💾保存')
      activePreset.value = undefined
      activeLabel.value = ''
      return
    }
    const last = savedList[savedList.length - 1]
    localPrompt.value = last.template
    activeLabel.value = last.label
    return
  }
  if (idx >= 0 && props.presets[idx]) {
    localPrompt.value = props.presets[idx].template
    activeLabel.value = props.presets[idx].label
  }
}

function saveCustom() {
  if (!localPrompt.value.trim()) return
  const savedList = JSON.parse(localStorage.getItem(props.storageKey) || '[]')
  const label = prompt('模板名称（如：我的精简分析）:')
  if (!label) return
  savedList.push({ label, template: localPrompt.value })
  localStorage.setItem(props.storageKey, JSON.stringify(savedList))
  activeLabel.value = label
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
