import { ref, computed } from 'vue'

const count = ref(0)

export const useGlobalLoading = () => {
  const isLoading = computed(() => count.value > 0)

  function start() {
    count.value++
  }

  function stop() {
    count.value = Math.max(0, count.value - 1)
  }

  function reset() {
    count.value = 0
  }

  return { isLoading, start, stop, reset }
}
