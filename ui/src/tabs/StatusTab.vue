<!-- Status tab: what duetLapse3 and the printer are doing, and the last image -->
<script setup>
import { computed } from "vue";
import { status } from "../status.js";
import { mdiCameraOff } from "../icons.js";

const s = computed(() => status.data);

const rows = computed(() => s.value ? [
	{ label: "duetLapse3 state", value: s.value.action },
	{ label: "Capture status", value: s.value.printState },
	{ label: "Printer status", value: s.value.connected ? s.value.duetStatus : "not connected" },
	{ label: "Images captured", value: s.value.camera2 || s.value.frames2 ? `Camera1 ${s.value.frames}, Camera2 ${s.value.frames2}` : s.value.frames },
	{ label: "Current layer", value: s.value.layer ?? "None" },
	{ label: "Video", value: s.value.videoMessage },
	{ label: "Printer", value: `${s.value.printer} (firmware ${s.value.printerVersion ?? "unknown"})` },
	{ label: "duetLapse3 version", value: s.value.version },
	{ label: "Process id", value: s.value.pid },
] : []);

// A new image url when the frame count changes, so the browser shows the latest image
const imageSrc = computed(() => s.value?.lastImage ? `${s.value.lastImage}&n=${s.value.frames}` : "");
</script>

<template>
	<v-row v-if="s">
		<v-col cols="12" md="5">
			<v-card>
				<v-card-title>Status</v-card-title>
				<v-table density="compact">
					<tbody>
						<tr v-for="row in rows" :key="row.label">
							<td class="text-medium-emphasis">{{ row.label }}</td>
							<td class="font-weight-medium">{{ row.value }}</td>
						</tr>
					</tbody>
				</v-table>
			</v-card>
		</v-col>
		<v-col cols="12" md="7">
			<v-card>
				<v-card-title>Last image</v-card-title>
				<v-card-text>
					<div class="dl3-media">
						<a v-if="imageSrc" :href="imageSrc" target="_blank"><img :src="imageSrc" alt="Last image"></a>
						<div v-else class="dl3-media-overlay">
							<v-icon :icon="mdiCameraOff" size="40"></v-icon>
							<span v-if="!s.camera1 && !s.camera2">No camera in use - set one on the Cameras tab</span>
							<span v-else>Waiting for the first image to be captured</span>
						</div>
					</div>
				</v-card-text>
			</v-card>
		</v-col>
	</v-row>
	<v-progress-linear v-else indeterminate color="primary"></v-progress-linear>
</template>
