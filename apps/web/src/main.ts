import './styles/global.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { VueQueryPlugin } from '@tanstack/vue-query';
import App from './App.vue';
import { router } from './router';
import { bindAuthBridge } from './stores/auth';

const app = createApp(App);

app.use(createPinia());
// Привязать auth-стор к API-клиенту до первой навигации/запроса.
bindAuthBridge();
app.use(router);
app.use(VueQueryPlugin);

app.mount('#app');
