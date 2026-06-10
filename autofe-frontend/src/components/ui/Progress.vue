<template>
  <div
    :class="cn(
      'relative h-4 w-full overflow-hidden rounded-lg bg-secondary shadow-inner',
      props.class
    )"
  >
    <div
      class="h-full w-full flex-1 bg-primary transition-all duration-300 ease-in-out"
      :style="{
        transform: `translateX(-${100 - (props.value || 0)}%)`,
      }"
    />
  </div>
</template>

<script setup lang="ts">
import { cn } from '@/lib/utils'

interface Props {
  class?: string
  value?: number
}

const props = withDefaults(defineProps<Props>(), {})
</script>