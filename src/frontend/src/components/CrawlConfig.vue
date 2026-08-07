<template>
  <div class="crawl-config">
    <el-form label-position="top" size="default">
      <el-form-item label="每次爬取最大论文数">
        <el-input-number
          v-model="settings.crawlConfig.maxPapersPerSource"
          :min="5"
          :max="200"
          :step="5"
        />
        <template #extra>
          <span class="form-hint">每个来源单次同步上限；默认来源使用公开元数据 API</span>
        </template>
      </el-form-item>

      <el-form-item label="请求间隔（秒）">
        <el-input-number
          v-model="settings.crawlConfig.requestInterval"
          :min="1"
          :max="30"
          :step="1"
        />
        <template #extra>
          <span class="form-hint">不同来源请求之间的最小间隔</span>
        </template>
      </el-form-item>

      <el-form-item label="超时时间（秒）">
        <el-input-number
          v-model="settings.crawlConfig.timeout"
          :min="5"
          :max="120"
          :step="5"
        />
        <template #extra>
          <span class="form-hint">单个请求的超时时间</span>
        </template>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
</script>

<style scoped>
.form-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
