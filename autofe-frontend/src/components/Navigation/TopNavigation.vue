<template>
  <div class="top-navigation">
    <div class="nav-left">
      <h1 class="welcome-title">Welcome to Adda</h1>
    </div>
    <div class="nav-right">
      <!-- 右侧可以添加其他功能按钮 -->
    </div>
  </div>
</template>

<style scoped>
.top-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  height: 4rem;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
}

.welcome-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.25rem;
  font-weight: 600;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .top-navigation {
    padding: 0.75rem 1rem;
  }

  .welcome-title {
    font-size: 1.125rem;
  }
}
</style>
