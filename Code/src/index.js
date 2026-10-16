'use strict'

import { registerRoute } from 'DuetWebControl';
import duetLapse3 from './duetLapse3.vue';

registerRoute(duetLapse3, {
  Plugins: {
    duetLapse3: {
      icon: 'mdi-transition',
      caption: 'duetLapse3',
      translated: true,
      path: '/Plugins/duetLapse3',
    },
  },
});
