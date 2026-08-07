<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="添加论文来源"
    width="480px"
    :close-on-click-modal="false"
  >
    <el-form label-position="top" @submit.prevent="handleAdd">
      <el-form-item label="网址">
        <el-input
          v-model="url"
          placeholder="https://arxiv.org/list/cs.AI/recent"
          clearable
        />
      </el-form-item>
      <p class="source-hint">当前默认支持 arXiv list/category URL，并通过公共 API 同步。</p>
      <el-form-item label="备注名（可选）">
        <el-input
          v-model="label"
          placeholder="如：arXiv cs.AI"
          clearable
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :disabled="!url.trim()" @click="handleAdd">
        添加
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible', 'add'])

const url = ref('')
const label = ref('')

watch(() => props.visible, (val) => {
  if (val) { url.value = ''; label.value = '' }
})

function handleAdd() {
  if (!url.value.trim()) return
  emit('add', url.value.trim(), label.value.trim())
  emit('update:visible', false)
}
</script>

<style scoped>
.source-hint { margin: -8px 0 14px; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
</style>
