<template>
  <div class="demo-container p-8 max-w-4xl mx-auto">
    <h2 class="demo-title">Shadcn-vue Components Demo</h2>

    <!-- 按钮示例 -->
    <div class="demo-section mb-6">
      <h3 class="demo-subtitle">Buttons</h3>
      <div class="flex flex-wrap gap-3">
        <Button variant="default">Default Button</Button>
        <Button variant="secondary">Secondary Button</Button>
        <Button variant="outline">Outline Button</Button>
        <Button variant="destructive">Destructive Button</Button>
      </div>
    </div>

    <!-- 输入框示例 -->
    <div class="demo-section mb-6">
      <h3 class="demo-subtitle">Input Fields</h3>
      <div class="space-y-4 max-w-md">
        <div>
          <label class="demo-label">Text Input</label>
          <Input placeholder="Enter some text..." />
        </div>
        <div>
          <label class="demo-label">Textarea</label>
          <textarea
            class="demo-textarea"
            placeholder="Enter multiple lines..."
          ></textarea>
        </div>
        <div>
          <label class="demo-label">Select</label>
          <select class="demo-select">
            <option>Option 1</option>
            <option>Option 2</option>
            <option>Option 3</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 徽章示例 -->
    <div class="demo-section mb-6">
      <h3 class="demo-subtitle">Badges</h3>
      <div class="flex flex-wrap gap-2">
        <Badge variant="default">Default</Badge>
        <Badge variant="secondary">Secondary</Badge>
        <Badge variant="success">Success</Badge>
        <Badge variant="warning">Warning</Badge>
        <Badge variant="info">Info</Badge>
        <Badge variant="destructive">Destructive</Badge>
      </div>
    </div>

    <!-- 进度条示例 -->
    <div class="demo-section mb-6">
      <h3 class="demo-subtitle">Progress Bar</h3>
      <div class="space-y-4 max-w-md">
        <div>
          <div class="flex justify-between mb-2">
            <span class="demo-text">Progress</span>
            <span class="demo-text">75%</span>
          </div>
          <Progress :value="75" />
        </div>
        <div>
          <div class="flex justify-between mb-2">
            <span class="demo-text">Loading</span>
            <span class="demo-text">40%</span>
          </div>
          <Progress :value="40" />
        </div>
      </div>
    </div>

    <!-- 卡片示例 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Feature Engineering</CardTitle>
        </CardHeader>
        <CardContent>
          <p class="demo-text">
            Automated feature engineering using LLM-driven agent collaboration and
            advanced machine learning techniques.
          </p>
          <div class="mt-4">
            <Badge variant="success">Active</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model Training</CardTitle>
        </CardHeader>
        <CardContent>
          <p class="demo-text">
            In-database ML computation with PostgreSQL and C++ UDFs for optimal
            performance and scalability.
          </p>
          <div class="mt-4">
            <Badge variant="warning">Processing</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <p class="demo-text">
            Real-time performance monitoring and optimization with comprehensive
            metrics and visualization tools.
          </p>
          <div class="mt-4">
            <Badge variant="info">Monitoring</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import Button from './Button.vue'
import Input from './Input.vue'
import Badge from './Badge.vue'
import Progress from './Progress.vue'
import Card from './Card.vue'
import CardHeader from './CardHeader.vue'
import CardTitle from './CardTitle.vue'
import CardContent from './CardContent.vue'
</script>

<style scoped>
.demo-container {
  min-height: 100vh;
  background-color: #f8fafc;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.demo-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 1.5rem;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.demo-section {
  background-color: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  border: 1px solid #e2e8f0;
  padding: 1.5rem;
  transition: all 0.2s ease;
}

.demo-section:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
}

.demo-subtitle {
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 1rem;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.demo-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #334155;
  margin-bottom: 0.25rem;
  display: block;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.demo-text {
  font-size: 0.875rem;
  color: #475569;
  line-height: 1.6;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

.demo-textarea {
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  background-color: white;
  outline: none;
  width: 100%;
  height: 6rem;
  resize: none;
}

.demo-textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.demo-select {
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
  background-color: white;
  outline: none;
  width: 100%;
}

.demo-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.space-y-4 > * + * {
  margin-top: 1rem;
}

.space-x-4 > * + * {
  margin-left: 1rem;
}
</style>