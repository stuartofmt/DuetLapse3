<!-- Log tab: the current logfile - its end, then new lines as they are written. Follow keeps the newest line in view.
     Previous shows the logfile from the run before this one instead, and download gets the logfile being shown -->
<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { api, fileUrl } from "../api.js";
import { t } from "../i18n.js";
import { changes, status } from "../status.js";
import { mdiDownload, mdiMagnify, mdiRefresh } from "../icons.js";

const MAX_LINES = 10000; // Older lines are dropped from the page - the logfile keeps them

const lines = ref([]);
const log = reactive({ loaded: false, enabled: true, file: "", previous: "", error: "", truncated: false });
const filter = ref("");
const follow = ref(true);
const loading = ref(false);
const box = ref(null);
const showPrevious = ref(false); // The logfile from the run before this one, instead of the current one
let offset = -1;
let number = 0; // Which logfile offset is in - a new print starts a new one
let again = false;

async function load() {
	if (loading.value) {
		again = true; // The log grew while reading it
		return;
	}
	loading.value = true;
	const previous = showPrevious.value;
	try {
		const data = await api.get(`/api/log?offset=${offset}&number=${number}${previous ? "&previous=true" : ""}`);
		if (previous !== showPrevious.value) return; // Switched while reading - read again (finally)
		Object.assign(log, { loaded: true, enabled: data.enabled, file: data.file ?? "", previous: data.previous ?? "", error: data.error ?? "" });
		if (data.enabled && !data.error) {
			const added = data.text ? data.text.replace(/\n$/, "").split("\n") : [];
			const all = data.reset ? added : [...lines.value, ...added];
			log.truncated = data.reset ? data.truncated : log.truncated || all.length > MAX_LINES;
			lines.value = all.slice(-MAX_LINES);
			offset = data.offset;
			number = data.number;
		}
	} catch (err) {
		Object.assign(log, { loaded: true, error: err.message });
	} finally {
		loading.value = false;
		if (again || previous !== showPrevious.value) {
			again = false;
			load();
		}
	}
}

// From the end of the logfile again - e.g. duetLapse3 restarted, so there is a new logfile
function reload() {
	offset = -1;
	load();
}

const text = computed(() => {
	const wanted = filter.value.trim().toLowerCase();
	return (wanted ? lines.value.filter((line) => line.toLowerCase().includes(wanted)) : lines.value).join("\n");
});

function toEnd() {
	if (box.value) {
		box.value.scrollTop = box.value.scrollHeight;
	}
}

// Scrolling up to read stops following, and scrolling back to the end starts it again
function scrolled() {
	const b = box.value;
	follow.value = b.scrollHeight - b.scrollTop - b.clientHeight < 20;
}

watch(text, async () => {
	if (follow.value) {
		await nextTick();
		toEnd();
	}
});
watch(follow, (on) => on && toEnd());
watch(showPrevious, () => {
	lines.value = [];
	Object.assign(log, { loaded: false, file: "", truncated: false, error: "" });
	follow.value = true;
	reload();
});
watch(() => changes.log, () => showPrevious.value || load()); // The previous logfile doesn't change
watch(() => status.data?.run, (run, before) => {
	if (before !== undefined && run !== before) {
		reload();
	}
});

onMounted(load);
</script>

<template>
	<v-card>
		<div class="d-flex flex-wrap align-center ga-2 pa-3">
			<v-text-field v-model="filter" :prepend-inner-icon="mdiMagnify" :placeholder="t('log.filter')" clearable
						  variant="outlined" density="compact" hide-details style="min-width: 180px; max-width: 320px"
						  @update:model-value="filter = $event ?? ''"></v-text-field>
			<v-spacer></v-spacer>
			<v-switch v-model="follow" :label="t('log.follow')" color="primary" density="compact" inset hide-details class="flex-grow-0 me-2"></v-switch>
			<v-btn :icon="mdiRefresh" variant="text" size="small" :loading="loading" :title="t('common.refresh')" @click="reload"></v-btn>
			<!-- Which logfile: the current one, or the one from the run before this one -->
			<v-btn-toggle v-if="log.previous || showPrevious" v-model="showPrevious" mandatory density="compact"
						  variant="outlined" color="primary" divided>
				<v-btn :value="false" size="small">{{ t("log.current") }}</v-btn>
				<v-btn :value="true" size="small">{{ t("log.previous") }}</v-btn>
			</v-btn-toggle>
			<v-btn :icon="mdiDownload" variant="text" size="small" :disabled="!log.file" :href="log.file ? fileUrl(log.file) : undefined"
				   :title="t('common.download')"></v-btn>
		</div>
		<v-divider></v-divider>
		<v-alert v-if="!log.enabled" type="info" variant="tonal" class="ma-3">{{ t("log.disabled") }}</v-alert>
		<v-alert v-else-if="log.error" type="error" variant="tonal" class="ma-3">{{ t("log.couldNotRead", { error: log.error }) }}</v-alert>
		<template v-else>
			<div v-if="log.truncated" class="text-caption text-medium-emphasis px-3 pt-2">{{ t("log.truncated") }}</div>
			<pre ref="box" class="dl3-log pa-3" @scroll.passive="scrolled">{{ text }}</pre>
			<div v-if="log.loaded && !text" class="text-center text-medium-emphasis pa-4">{{ filter ? t("log.noMatch", { filter }) : t("log.empty") }}</div>
			<div v-if="log.file" class="text-caption text-medium-emphasis px-3 pb-2 dl3-break">{{ log.file }}</div>
		</template>
	</v-card>
</template>

<style scoped>
.dl3-log {
	height: calc(100vh - 258px);
	min-height: 300px;
	overflow: auto;
	margin: 0;
	font-family: ui-monospace, Consolas, "DejaVu Sans Mono", monospace;
	font-size: 12px;
	line-height: 1.45;
	white-space: pre;
}
</style>
