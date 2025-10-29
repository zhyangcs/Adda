import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Bootstrap CSS
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

// Splitpanes
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// Register splitpanes components globally
app.component('Splitpanes', Splitpanes)
app.component('Pane', Pane)

app.mount('#app')
