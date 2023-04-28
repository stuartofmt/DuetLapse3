//Thanks to @MintyTrebor for all the help in getting this working
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
 
<template>
		<div class="iframe_container">
			<iframe :src= "myurl" width="100%" :height="tmpHeight" frameborder="0">
				<span>Your browser does not support iFrames</span>
			</iframe>
		</div>
</template>
 
<script>
import Path from '@/utils/path';
import store from "@/store";
import { DisconnectedError, OperationCancelledError } from "@/utils/errors";
 
const version = '0.0.1';
const configFile = './DuetLapse3/DuetLapse3.config';
 
export default {
	data() { 
		return{
			version: version,
			myurl: '',
			tmpHeight: "400px",
			fileContent: ""
		};
	},
	methods: {		
        //Modified file load from @mintyTrebor 
		async loadSettingsFromFile() {
			//Load the DuetLapse3.config file
			try {
				const setFileName = Path.combine(this.systemDirectory, configFile);
				const response = await store.dispatch("machine/download", { filename: setFileName, type: 'text', showSuccess: false, showError: false});
				this.fileContent = await response;
				//get the ip address
				let pattern = /-duet.*(?:$|\n)/i;
				let match = this.fileContent.match(pattern).toString();
				this.myurl = "http://"+ match.replace('-duet', '').trim();
				// get the port
				pattern = /-port.*(?:$|\n)/i;
				match = this.fileContent.match(pattern).toString();
				this.myurl = this.myurl + ":" + match.replace('-port', '').trim();
				console.log('DuetLapse url is ' + this.myurl);
 
			} catch (e) {
				if (!(e instanceof DisconnectedError) && !(e instanceof OperationCancelledError)) {
					console.warn(e);
					console.warn("File Does Not Exist");
				}
			}
		},
		getAvailScreenHeight(){
		let tmpHeight = window.innerHeight - 90;
		if(window.document.getElementById("global-container")){
			tmpHeight = tmpHeight - window.document.getElementById("global-container").offsetHeight;
		}
		if(this.showBottomNavigation) {
			tmpHeight = tmpHeight - 56;
		}
		return tmpHeight;
	}
	},
	
	// use computed instead of methods cuz we only want it to run once
	computed:{
		systemDirectory() {
			return store.state.machine.model.directories.system;
		},
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
		this.getAvailScreenHeight();
	},
 
 
}	
</script>
 
