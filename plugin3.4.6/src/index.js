'use strict'

import { registerRoute } from '../../routes'

import DuetLapse3 from './DuetLapse3.vue'
//import Vue from 'vue';

// Register a route via Plugins -> DuetLapse3
registerRoute(DuetLapse3, {
	Plugins: {
		DuetLapse3: {
			icon: 'mdi-transition',
			caption: 'DuetLapse3',
			path: '/DuetLapse3'
		}
	}
});
