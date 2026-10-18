<!-- Status tab: the controls, what duetLapse3 and the printer are doing, and the last image -->
<script setup>
import { computed } from "vue";
import { status } from "../status.js";
import { serverText, t, valueText } from "../i18n.js";
import ControlsCard from "../components/ControlsCard.vue";
import { mdiCameraOff } from "../icons.js";

const s = computed(() => status.data);

const rows = computed(() => s.value ? [
	{ label: t("status.state"), value: valueText("action", s.value.action) },
	{ label: t("status.capture"), value: valueText("printState", s.value.printState) },
	{ label: t("status.printerStatus"), value: s.value.connected ? valueText("duetStatus", s.value.duetStatus) : t("status.notConnected") },
	{ label: t("status.images"), value: s.value.camera2 || s.value.frames2 ? t("status.imagesTwo", { frames: s.value.frames, frames2: s.value.frames2 }) : s.value.frames },
	{ label: t("status.layer"), value: s.value.layer ?? t("status.none") },
	{ label: t("status.video"), value: serverText(s.value.videoMessage, s.value.videoMessageCode) },
	{ label: t("status.printer"), value: t("status.printerValue", { printer: s.value.printer, version: s.value.printerVersion ?? t("status.unknown") }) },
	{ label: t("status.version"), value: s.value.version },
] : []);

// A new image url when the frame count changes, so the browser shows the latest image
const imageSrc = computed(() => s.value?.lastImage ? `${s.value.lastImage}&n=${s.value.frames}` : "");
</script>

<template>
	<v-row v-if="s">
		<v-col cols="12" md="5">
			<ControlsCard class="mb-4"></ControlsCard>
			<v-card>
				<v-card-title>{{ t("status.title") }}</v-card-title>
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
				<v-card-title>{{ t("status.lastImage") }}</v-card-title>
				<v-card-text>
					<div class="dl3-media">
						<a v-if="imageSrc" :href="imageSrc" target="_blank"><img :src="imageSrc" :alt="t('status.lastImage')"></a>
						<div v-else class="dl3-media-overlay">
							<v-icon :icon="mdiCameraOff" size="40"></v-icon>
							<span v-if="!s.camera1 && !s.camera2">{{ t("status.noCamera") }}</span>
							<span v-else>{{ t("status.waiting") }}</span>
						</div>
					</div>
				</v-card-text>
			</v-card>
		</v-col>
	</v-row>
	<v-progress-linear v-else indeterminate color="primary"></v-progress-linear>
</template>
