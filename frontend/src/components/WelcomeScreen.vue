<script setup lang="ts">
import SwooshMark from './SwooshMark.vue'

const emit = defineEmits<{ suggestion: [msg: string] }>()
const suggestions = [
  '推荐一款跑步鞋',
  'Air Force 1 多少钱？',
  '退货流程是怎样的？',
  '帮我查一下订单 DD20240725001',
]
</script>

<template>
  <div class="welcome">
    <div class="hero">
      <span class="hero-mark"><SwooshMark :size="42" :weight="3.6" /></span>
      <h1 class="hero-title">你好，我是<em>小速</em></h1>
    </div>
    <p class="hero-sub">耐克官方旗舰店的智能客服。查订单、退换货、选鞋……都可以问我。</p>
    <div class="tags">
      <button v-for="s in suggestions" :key="s" class="tag" @click="emit('suggestion', s)">
        {{ s }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.welcome { text-align: center; padding: clamp(56px, 12vh, 110px) 16px 24px; }
.hero { display: flex; flex-direction: column; align-items: center; gap: 20px; }
.hero-mark {
  width: 84px; height: 84px;
  border-radius: 24px;
  background: var(--signal);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  transform: rotate(-2deg);
  box-shadow: 0 16px 36px -16px var(--signal);
}
.hero-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(34px, 6vw, 52px);
  line-height: 1.15;
  margin: 0;
  letter-spacing: 1px;
}
.hero-title em { font-style: normal; color: var(--signal); }
.hero-sub { color: var(--ink-soft); font-size: 15px; margin: 14px 0 26px; }
.tags { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; max-width: 560px; margin: 0 auto; }
.tag {
  font: 13.5px var(--font-body);
  color: var(--ink-soft);
  background: var(--surface);
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--r-full);
  padding: 7px 16px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, transform 0.15s var(--ease), box-shadow 0.15s;
}
.tag:hover {
  border-color: var(--signal);
  color: var(--signal);
  transform: translateY(-1px);
  box-shadow: var(--shadow-card);
}
</style>
