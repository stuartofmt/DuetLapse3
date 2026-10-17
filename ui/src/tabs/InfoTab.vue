<!-- Info tab: where things are, and the settings in use -->
<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";

const info = ref(null);

onMounted(async () => {
	try {
		info.value = await api.get("/api/info");
	} catch (err) {
		notify(`Could not read the information: ${err.message}`, "error", 6000);
	}
});
</script>

<template>
	<v-row v-if="info">
		<v-col cols="12" md="6">
			<v-card>
				<v-card-title>duetLapse3</v-card-title>
				<v-table density="compact">
					<tbody>
						<tr>
							<td class="text-medium-emphasis">This page</td>
							<td class="dl3-break"><a :href="info.pageAddress" target="_blank" class="text-primary">{{ info.pageAddress }}</a></td>
						</tr>
						<tr><td class="text-medium-emphasis">Process id</td><td>{{ info.pid }}</td></tr>
						<tr><td class="text-medium-emphasis">Settings file</td><td class="dl3-break">{{ info.configFile }}</td></tr>
						<tr><td class="text-medium-emphasis">Log file</td><td class="dl3-break">{{ info.logFile }}</td></tr>
						<tr><td class="text-medium-emphasis">Images and videos</td><td class="dl3-break">{{ info.topDir }}</td></tr>
						<tr>
							<td class="text-medium-emphasis">Images for this print</td>
							<td class="dl3-break">{{ info.imageLocation || "Waiting for the first image" }}</td>
						</tr>
					</tbody>
				</v-table>
			</v-card>
		</v-col>
		<v-col cols="12" md="6">
			<v-card>
				<v-card-title>Settings in use</v-card-title>
				<v-table density="compact">
					<tbody>
						<tr v-for="option in info.options" :key="option.label">
							<td class="text-medium-emphasis">{{ option.label }}</td>
							<td class="dl3-break">{{ option.value }}</td>
						</tr>
					</tbody>
				</v-table>
			</v-card>
		</v-col>
	</v-row>
	<v-progress-linear v-else indeterminate color="primary"></v-progress-linear>
</template>
