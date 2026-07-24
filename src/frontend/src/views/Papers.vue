<template>
  <div class="papers-page">
    <h1 class="page-title">论文中心</h1>

    <!-- Progress -->
    <CrawlProgress
      :status="crawlStatus"
      :percentage="crawlPercentage"
      :message="crawlMessage"
    />

    <!-- Area 1: Crawl Control -->
    <CrawlControl
      :sources="journalSources"
      @add-source="showAddDialog = true"
      @delete-source="handleDeleteSource"
      @crawl-start="handleCrawlStart"
    />

    <!-- Area 2: AI Review -->
    <AIReviewCard :review="aiReview" />

    <!-- Area 3: Filter + Paper List -->
    <PaperFilterBar @filter-change="handleFilter" />

    <div v-if="filteredPapers.length === 0" class="empty-state">
      <div class="empty-state-icon">📄</div>
      <p>暂无论文数据</p>
      <p class="text-small text-secondary">添加期刊源后点击爬取按钮</p>
    </div>

    <TransitionGroup v-else name="fade" tag="div">
      <PaperCard
        v-for="paper in filteredPapers"
        :key="paper.id"
        :paper="paper"
        @toggle-cart="handleToggleCart(paper)"
        @view-detail="openDetail(paper)"
      />
    </TransitionGroup>

    <!-- Pagination placeholder -->
    <div v-if="filteredPapers.length > 0" class="pagination-row flex-center">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="filteredPapers.length"
        layout="prev, pager, next"
        small
      />
    </div>

    <!-- Dialogs -->
    <AddSourceDialog
      v-model:visible="showAddDialog"
      @add="handleAddSource"
    />

    <PaperDetailModal
      v-model:visible="showDetail"
      :paper="selectedPaper"
      @toggle-cart="handleToggleCart"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import CrawlControl from '@/components/CrawlControl.vue'
import CrawlProgress from '@/components/CrawlProgress.vue'
import AIReviewCard from '@/components/AIReviewCard.vue'
import PaperFilterBar from '@/components/PaperFilterBar.vue'
import PaperCard from '@/components/PaperCard.vue'
import PaperDetailModal from '@/components/PaperDetailModal.vue'
import AddSourceDialog from '@/components/AddSourceDialog.vue'
import { useCartStore } from '@/stores/cart'

const cartStore = useCartStore()

// ---- Mock Data ----
let nextSourceId = 5
let nextPaperId = 7

const journalSources = ref([
  { id: 1, url: 'https://arxiv.org/list/cs.AI/recent', label: 'arXiv cs.AI', last_crawled_at: '2026-07-20', last_paper_count: 12 },
  { id: 2, url: 'https://arxiv.org/list/cs.CV/recent', label: 'arXiv cs.CV', last_crawled_at: '2026-07-19', last_paper_count: 8 },
  { id: 3, url: 'https://openaccess.thecvf.com/CVPR2024', label: 'CVPR 2024', last_crawled_at: null, last_paper_count: null },
  { id: 4, url: 'https://proceedings.neurips.cc/paper_files/paper/2024', label: 'NeurIPS 2024', last_crawled_at: '2026-07-15', last_paper_count: 0 },
])

const papers = ref([
  {
    id: 1,
    title: 'Attention Is All You Need',
    authors: ['Vaswani', 'Shazeer', 'Parmar', 'Uszkoreit', 'Jones', 'Gomez', 'Kaiser', 'Polosukhin'],
    journal_name: 'NeurIPS',
    publish_year: 2017,
    arxiv_id: '1706.03762',
    paper_url: 'https://arxiv.org/abs/1706.03762',
    has_code: true,
    code_url: 'https://github.com/tensorflow/tensor2tensor',
    ai_innovation: '提出纯注意力机制的 Transformer 架构，完全摒弃 RNN 和 CNN，实现并行化序列建模，大幅提升训练效率和长距离依赖建模能力。',
    ai_technologies: ['Self-Attention', 'Multi-Head Attention', 'Positional Encoding', 'Layer Normalization', 'Dropout', 'Label Smoothing'],
    abstract: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
    in_cart: false,
  },
  {
    id: 2,
    title: 'CLIP: Learning Transferable Visual Models From Natural Language Supervision',
    authors: ['Radford', 'Kim', 'Hallacy', 'Ramesh', 'Goh', 'Agarwal', 'Sastry', 'Askell', 'Mishkin', 'Clark', 'Krueger', 'Sutskever'],
    journal_name: 'ICML',
    publish_year: 2021,
    arxiv_id: '2103.00020',
    paper_url: 'https://arxiv.org/abs/2103.00020',
    has_code: true,
    code_url: 'https://github.com/openai/CLIP',
    ai_innovation: '提出使用对比学习联合训练图像和文本编码器，在零样本图像分类上取得突破性成果，证明自然语言监督可用于学习高质量的视觉表示。',
    ai_technologies: ['Contrastive Learning', 'Vision Transformer', 'Zero-shot Learning', 'Multi-modal Learning', 'Natural Language Supervision'],
    abstract: 'State-of-the-art computer vision systems are trained to predict a fixed set of predetermined object categories. This restricted form of supervision limits their generality and usability. We demonstrate that predicting which caption goes with which image is an efficient and scalable way to learn SOTA image representations from scratch.',
    in_cart: true,
  },
  {
    id: 3,
    title: 'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding',
    authors: ['Devlin', 'Chang', 'Lee', 'Toutanova'],
    journal_name: 'NAACL',
    publish_year: 2019,
    arxiv_id: '1810.04805',
    paper_url: 'https://arxiv.org/abs/1810.04805',
    has_code: true,
    code_url: 'https://github.com/google-research/bert',
    ai_innovation: '提出基于 Masked Language Model 和 Next Sentence Prediction 的双向预训练方法，在 11 项 NLP 基准上刷新记录。',
    ai_technologies: ['Masked LM', 'Next Sentence Prediction', 'Transformer Encoder', 'Pre-training + Fine-tuning', 'WordPiece Tokenization'],
    abstract: 'We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.',
    in_cart: false,
  },
  {
    id: 4,
    title: 'A Theoretical Analysis of Reinforcement Learning from Human Feedback',
    authors: ['Smith', 'Johnson'],
    journal_name: 'arXiv preprint',
    publish_year: 2024,
    arxiv_id: '2401.12345',
    paper_url: null,
    has_code: false,
    code_url: null,
    ai_innovation: '对 RLHF 的收敛性进行了严格的理论分析，证明了在某些条件下 PPO 可以收敛到局部最优解，并给出了样本复杂度的上界。',
    ai_technologies: ['RLHF', 'PPO', 'Reward Modeling', 'Convergence Analysis', 'Sample Complexity'],
    abstract: 'Reinforcement Learning from Human Feedback (RLHF) has emerged as a crucial technique for aligning large language models. Despite its empirical success, theoretical understanding remains limited. In this work, we provide rigorous convergence guarantees for RLHF...',
    in_cart: false,
  },
  {
    id: 5,
    title: 'ImageNet Classification with Deep Convolutional Neural Networks',
    authors: ['Krizhevsky', 'Sutskever', 'Hinton'],
    journal_name: 'NeurIPS',
    publish_year: 2012,
    arxiv_id: null,
    paper_url: 'https://papers.nips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html',
    has_code: false,
    code_url: null,
    ai_innovation: '首次在大规模图像分类上成功应用深度卷积神经网络，利用 GPU 加速训练，大幅降低 ImageNet 分类错误率，开启了深度学习时代。',
    ai_technologies: ['CNN', 'ReLU', 'Dropout', 'Data Augmentation', 'GPU Training', 'ImageNet'],
    abstract: 'We trained a large, deep convolutional neural network to classify the 1.2 million high-resolution images in the ImageNet LSVRC-2010 contest into the 1000 different classes...',
    in_cart: false,
  },
  {
    id: 6,
    title: 'Denoising Diffusion Probabilistic Models',
    authors: ['Ho', 'Jain', 'Abbeel'],
    journal_name: 'NeurIPS',
    publish_year: 2020,
    arxiv_id: '2006.11239',
    paper_url: 'https://arxiv.org/abs/2006.11239',
    has_code: true,
    code_url: 'https://github.com/hojonathanho/diffusion',
    ai_innovation: '证明扩散概率模型可以生成高质量的图像，建立了去噪分数匹配和扩散模型之间的理论联系，成为 DALL-E 2 和 Stable Diffusion 的基础。',
    ai_technologies: ['Diffusion Models', 'Denoising Score Matching', 'Langevin Dynamics', 'U-Net', 'Noise Schedule'],
    abstract: 'We present high quality image synthesis results using diffusion probabilistic models, a class of latent variable models inspired by considerations from nonequilibrium thermodynamics...',
    in_cart: true,
  },
])

const aiReview = {
  total_papers: 45,
  sources_count: 3,
  with_code_count: 23,
  hot_topics: '大模型推理优化、多模态对齐与融合、AI Agent 自主协作、扩散模型加速采样',
  recommendations: [
    { title: 'Attention Is All You Need', reason: 'Transformer 原始论文，所有 LLM 的基础' },
    { title: 'CLIP: Connecting Text and Images', reason: '多模态学习的里程碑，零样本泛化能力突出' },
    { title: 'Denoising Diffusion Probabilistic Models', reason: '扩散模型开山之作，理论与实践的完美结合' },
  ],
  tech_trends: 'LoRA 微调、RLHF 对齐、Chain-of-Thought 推理、Retrieval-Augmented Generation (RAG)、Mixture of Experts (MoE) 出现频繁',
}

// ---- State ----
const showAddDialog = ref(false)
const showDetail = ref(false)
const selectedPaper = ref(null)
const page = ref(1)
const pageSize = 20

const crawlStatus = ref('done')
const crawlPercentage = ref(0)
const crawlMessage = ref('')

const filters = ref({ search: '', hasCode: false, inCart: false, sort: 'newest' })

// ---- Computed ----
const filteredPapers = computed(() => {
  let result = [...papers.value]

  if (filters.value.search) {
    const q = filters.value.search.toLowerCase()
    result = result.filter((p) =>
      p.title.toLowerCase().includes(q) ||
      p.authors.some((a) => a.toLowerCase().includes(q))
    )
  }
  if (filters.value.hasCode) result = result.filter((p) => p.has_code)
  if (filters.value.inCart) result = result.filter((p) => p.in_cart)

  if (filters.value.sort === 'newest') result.sort((a, b) => b.publish_year - a.publish_year)
  else if (filters.value.sort === 'oldest') result.sort((a, b) => a.publish_year - b.publish_year)
  else if (filters.value.sort === 'title_asc') result.sort((a, b) => a.title.localeCompare(b.title))

  return result
})

// ---- Actions ----
function openDetail(paper) {
  selectedPaper.value = paper
  showDetail.value = true
}

function handleToggleCart(paper) {
  if (paper.in_cart) {
    cartStore.removeItem(paper.id)
    paper.in_cart = false
  } else {
    cartStore.addItem({ ...paper, in_cart: true })
    paper.in_cart = true
  }
}

function handleFilter(f) {
  filters.value = f
  page.value = 1
}

function handleAddSource(url, label) {
  journalSources.value.push({
    id: nextSourceId++,
    url,
    label: label || url,
    last_crawled_at: null,
    last_paper_count: null,
  })
}

function handleDeleteSource(id) {
  journalSources.value = journalSources.value.filter((s) => s.id !== id)
}

function handleCrawlStart(sourceIds, mode) {
  crawlStatus.value = 'crawling'
  crawlPercentage.value = 0
  crawlMessage.value = ''

  // Simulate crawl progress
  const interval = setInterval(() => {
    crawlPercentage.value += 20
    if (crawlPercentage.value >= 60) {
      crawlStatus.value = 'analyzing'
    }
    if (crawlPercentage.value >= 100) {
      crawlStatus.value = 'done'
      crawlMessage.value = `从 ${sourceIds.length} 个源爬取完成，新增 6 篇论文，AI 分析完毕`
      clearInterval(interval)

      // update source last_crawled timestamps
      journalSources.value.forEach((s) => {
        if (sourceIds.includes(s.id)) {
          s.last_crawled_at = new Date().toISOString().slice(0, 10)
          s.last_paper_count = Math.floor(Math.random() * 15) + 1
        }
      })
    }
  }, 600)
}
</script>

<style scoped>
.papers-page {
  padding-top: var(--space-lg);
}

.pagination-row {
  padding: var(--space-lg) 0;
}
</style>
