<--!
Displays an iFrame that is linked to the DuetLapse3 html Display
Polls the status of the sbcPlugin and terminates the DWC plugin if the sbcPlugin is terminated
Thanks to @MintyTrebor for all the help in getting this working
-->
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
			<iframe id="myiframe" :src= "myurl" width="100%" :height="tmpHeight" frameborder="0">
				<span>Your browser does not support iFrames</span>
			</iframe>
		</div>
</template>
 
<script>
import Path from '@/utils/path';
import store from "@/store";
import { DisconnectedError, OperationCancelledError } from "@/utils/errors";

// <!-- Do not change
const pluginName = 'DuetLapse3';
const configFile = './' + pluginName + '/' + pluginName + '.config';
// -->
window.onmessage = function(event){
    if (event.data == 'reply') {
        console('Reply received!');
    }
};
export default {
	data() { 
		return{
			myurl: '',
			tmpHeight: "400px",
		}
	},
	methods: {		
        //Modified file load from @mintyTrebor 
		async loadSettingsFromFile() {
			try {
				const setFileName = Path.combine(this.systemDirectory, configFile);
				const response = await store.dispatch("machine/download", { filename: setFileName, type: 'text', showSuccess: false, showError: false});
				this.fileContent = await response;
				//get the ip address
				let pattern = /-duet.*(?:$|\n)/i;
				let match = this.fileContent.match(pattern).toString();
				this.topurl = "http://"+ match.replace('-duet', '').trim();
				// get the port
				pattern = /-port.*(?:$|\n)/i;
				match = this.fileContent.match(pattern).toString();
				this.myurl = this.topurl + ":" + match.replace('-port', '').trim();
				console.log('DuetLapse url is ' + this.myurl);
 
			} catch (e) {
				if (!(e instanceof DisconnectedError) && !(e instanceof OperationCancelledError)) {
					console.warn(e);
					console.warn("File Does Not Exist");
				}
			}
		},
		// Set the screen height - from @MintyTrebor
		getAvailScreenHeight(){
		let tmpHeight = window.innerHeight - 90;
		if(window.document.getElementById("global-container")){
			tmpHeight = tmpHeight - window.document.getElementById("global-container").offsetHeight;
		}
		if(this.showBottomNavigation) {
			tmpHeight = tmpHeight - 56;
		}
		return tmpHeight;
		},
		// Check to see if the sbcExecutable is running - if not close the DWC side of the plugin
		checkExecutable(){
		let self = this;
		setInterval(function() {self.checkRunning();},5000); // Check every 5 seconds
		},
		checkRunning(){
		let self = this;
		if (self.isrunning()){
			return;
		}
		self.stopthePlugin();
		},
		async stopthePlugin(){
			// console.log('Stopping the plugin');
			store.dispatch("machine/unloadDwcPlugin", pluginName); // Unload the plugin
		},
		// sbc Executable is running if pid > 0
		isrunning() {
		const allplugins = store.state.machine.model.plugins;
		for (let [key, value] of allplugins) {
    		//console.log(key, value);
			if (key == pluginName){
				//console.log('Pid = ' + value.pid);
				if (value.pid > 0){
					return true
				};
				return false;
			};
		};
		}
	},	
	// use computed instead of methods cuz we only want it to run once
	computed:{
		systemDirectory() {
			return store.state.machine.model.directories.system;
		},
		showBottomNavigation() {
		return this.$vuetify.breakpoint.mobile && !this.$vuetify.breakpoint.xsOnly && this.$store.state.settings.bottomNavigation;
		}
	},
	mounted() {
		this.loadSettingsFromFile();
		this.getAvailScreenHeight();
		this.checkExecutable();
	} 
}
</script>
 
