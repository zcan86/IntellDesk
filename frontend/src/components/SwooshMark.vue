<script setup lang="ts">
// 签名元素：橙色勾形 swoosh —— 呼应耐克 swoosh，也代表"小速 = 迅捷"
withDefaults(defineProps<{ size?: number; weight?: number }>(), { size: 18, weight: 3.2 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M4.2 13.8 C 7.4 16.4 11 16.1 14.2 12.6 L 20 6.2"
      stroke="currentColor"
      :stroke-width="weight"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>
