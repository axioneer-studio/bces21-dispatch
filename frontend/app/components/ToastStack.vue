<script setup lang="ts">
const { toasts, dismiss, pause, resume } = useToastStore()
</script>

<template>
  <ClientOnly>
    <Teleport to="body">
      <div class="bces-toast-stack" role="region" aria-label="Notifications">
        <TransitionGroup
          name="bces-toast"
          tag="div"
          class="bces-toast-stack__list"
          appear
        >
          <div
            v-for="toast in toasts"
            :key="toast.id"
            class="bces-toast"
            :data-type="toast.type"
            role="status"
            @mouseenter="pause(toast.id)"
            @mouseleave="resume(toast.id)"
          >
            <button
              type="button"
              class="bces-toast__close"
              aria-label="Fermer la notification"
              @click="dismiss(toast.id)"
            >
              <Icon name="lucide:x" size="16" />
            </button>
            <div class="bces-toast__body">
              <p v-if="toast.title" class="bces-toast__title">{{ toast.title }}</p>
              <p class="bces-toast__message">{{ toast.message }}</p>
            </div>
            <div
              v-if="toast.duration > 0"
              class="bces-toast__progress"
              :style="{ animationDuration: `${toast.duration}ms` }"
              :data-paused="toast.paused ? '1' : '0'"
              aria-hidden="true"
            />
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
  </ClientOnly>
</template>