<script setup lang="ts">
const emit = defineEmits<{ suggestion: [msg: string] }>()
const suggestions = [
  '帮我查一下订单 DD20240001',
  '退货流程是怎样的？',
  '有没有蓝牙耳机推荐？',
  '满多少包邮？',
]
</script>

<template>
  <div class="welcome">
    <div class="icon">shopping_cart</div>
    <h2>你好！我是小速</h2>
    <p>速购电商智能客服。你可以问我：</p>
    <div class="suggestions">
      <el-button v-for="s in suggestions" :key="s" class="suggestion" round @click="emit('suggestion', s)">{{ s }}</el-button>
    </div>
  </div>
</template>

<style scoped>
.welcome { text-align: center; padding: 60px 20px 30px; }
.icon { font-size: 56px; margin-bottom: 12px; }
h2 { font-size: 22px; margin-bottom: 8px; }
p { color: #6e6e80; font-size: 14px; margin-bottom: 20px; }
.suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 520px; margin: 0 auto; }
</style>