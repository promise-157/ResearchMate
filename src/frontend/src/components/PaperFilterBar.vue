<template>
  <div class="filter-bar">
    <el-input
      v-model="search"
      placeholder="搜索标题、作者、关键词..."
      clearable
      :prefix-icon="Search"
      class="search-input"
      @input="emitFilter"
    />
    <div class="filter-toggles">
      <el-checkbox v-model="hasCode" @change="emitFilter">
        有代码
      </el-checkbox>
      <el-checkbox v-model="inCart" @change="emitFilter">
        已保存
      </el-checkbox>
      <el-select
        v-model="sort"
        placeholder="排序"
        class="sort-select"
        @change="emitFilter"
      >
        <el-option label="最新优先" value="newest" />
        <el-option label="最早优先" value="oldest" />
        <el-option label="标题 A-Z" value="title_asc" />
      </el-select>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'

const emit = defineEmits(['filter-change'])

const search = ref('')
const hasCode = ref(false)
const inCart = ref(false)
const sort = ref('newest')

function emitFilter() {
  emit('filter-change', {
    search: search.value,
    hasCode: hasCode.value,
    inCart: inCart.value,
    sort: sort.value,
  })
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
  flex-wrap: wrap;
}

.search-input {
  width: 280px;
}

.filter-toggles {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.sort-select {
  width: 130px;
}
</style>
