<template>
  <h3
    :class="cn(
      'text-lg font-semibold leading-none tracking-tight font-sans text-gray-900',
      props.class
    )"
  >
    <slot />
  </h3>
</template>

<script setup lang="ts">
import { cn } from '@/lib/utils'

interface Props {
  class?: string
}

const props = withDefaults(defineProps<Props>(), {})
</script>