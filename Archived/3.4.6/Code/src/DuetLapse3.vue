<template>
	<div class="iframe-container">
	  <iframe :src="myurl" width="100%" :height="tmpHeight" frameborder="0">
		<span>Your browser does not support iFrames</span>
	  </iframe>
	</div>
  </template>
  
  <style scoped>
  .iframe-container {
	position: relative;
	background-color: transparent;
  }
  
  .iframe-container iframe {
	position: absolute;
	top: 0;
	left: 0;
  }
  </style>
  
  <script>
  import { mapState, mapActions } from 'vuex';
  import Path from '../../utils/path.js';
  import { DisconnectedError, OperationCancelledError } from '../../utils/errors.js';
  
  const version = '0.0.1';
  const configFile = './DuetLapse3/DuetLapse3.config';
  
  export default {
	data() {
	  return {
		version: version,
		myurl: '',
		tmpHeight: '400px'
	  };
	},
	methods: {
	  ...mapActions('machine', { machineDownload: 'download' }),
  
	  // File load from @mintyTrebor modified with return
	  async loadSettingsFromFile() {
		// Load the DuetLapse3.config file
		try {
		  const setFileName = Path.combine(this.systemDirectory, configFile);
		  const response = await this.machineDownload({ filename: setFileName, type: 'text', showSuccess: false, showError: false });
		  this.fileContent = await response;
		  // Get the IP address
		  let pattern = /-duet.*(?:$|\n)/i;
		  let match = this.fileContent.match(pattern).toString();
		  this.myurl = 'http://' + match.replace('-duet', '').trim();
		  // Get the port
		  pattern = /-port.*(?:$|\n)/i;
		  match = this.fileContent.match(pattern).toString();
		  this.myurl = this.myurl + ':' + match.replace('-port', '').trim();
		  console.log('DuetLapse URL is ' + this.myurl);
		} catch (e) {
		  if (!(e instanceof DisconnectedError) && !(e instanceof OperationCancelledError)) {
			console.warn(e);
			console.warn('File Does Not Exist');
		  }
		}
	  },
	  getAvailScreenHeight() {
		let tmpHeight = window.innerHeight - 90;
		if (window.document.getElementById('global-container')) {
		  tmpHeight = tmpHeight - window.document.getElementById('global-container').offsetHeight;
		}
		if (this.showBottomNavigation) {
		  tmpHeight = tmpHeight - 56;
		}
		return tmpHeight;
	  }
	},
	computed: {
	  ...mapState('machine/model', {
		systemDirectory: (state) => state.directories.system
	  }),
	  showBottomNavigation() {
		return this.$vuetify.breakpoint.mobile && !this.$vuetify.breakpoint.xsOnly && this.$store.state.settings.bottomNavigation;
	  },
	  theurl() {
		return this.myurl;
	  },
	  theheight() {
		return this.tmpHeight;
	  }
	},
	mounted() {
	  this.loadSettingsFromFile();
	  this.tmpHeight = this.getAvailScreenHeight() + 'px';
	}
  };
  </script>
  