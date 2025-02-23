'use strict'

// import { registerRoute } from '../../routes'
import { registerRoute } from '@/routes'

//import Vue from 'vue';
import DuetLapse3 from './DuetLapse3.vue'


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