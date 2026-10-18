<!--
	The saved settings, one card per section, with an input to suit each setting's type.
	Every card's Save button saves the whole form. tab picks the sections (see /api/settings).
-->
<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
import { changes } from "../status.js";
import { choiceText, sectionTitle, serverText, settingDescription, settingLabel, t } from "../i18n.js";
import { mdiContentSave, mdiEye, mdiEyeOff } from "../icons.js";

const props = defineProps({
	tab: { type: String, required: true },      // config or video
	saveUrl: { type: String, required: true },
	check: { type: Function, default: null },   // (values) => { setting: error } for checks across settings
	limits: { type: Function, default: null },  // (values, key) => { min, max } for a number setting's arrows
});
const emit = defineEmits(["saved"]);

const sections = ref([]);
const values = reactive({});
const errors = reactive({});
const alert = reactive({ text: "", type: "success" });
const saving = ref(false);
const showPassword = ref(false);
const loaded = ref("");  // The values as last loaded - to tell whether they have been edited
const edited = computed(() => JSON.stringify(values) !== loaded.value);

// The settings were saved (here, on another tab, or in another browser) - show them, unless they are being edited here
watch(() => changes.settings, () => {
	if (!edited.value && !saving.value) {
		load();
	}
});

// Errors from checks across settings, shown as the values are typed
const crossErrors = computed(() => (props.check ? props.check(values) : {}));
const errorFor = (key) => errors[key] || crossErrors.value[key];
const limitsFor = (key) => ({ min: 0, ...(props.limits ? props.limits(values, key) : {}) });

function setErrors(newErrors = {}) {
	Object.keys(errors).forEach((key) => delete errors[key]);
	Object.assign(errors, newErrors);
}

async function load() {
	try {
		const data = await api.get(`/api/settings?tab=${props.tab}`);
		sections.value = data.sections;
		for (const section of data.sections) {
			for (const setting of section.settings) {
				values[setting.key] = setting.type === "list" ? [...setting.value] : setting.value;
			}
		}
		loaded.value = JSON.stringify(values);
		if (data.error) {
			Object.assign(alert, { text: serverText(data.error, data.errorCode), type: "error" });
		}
	} catch (err) {
		Object.assign(alert, { text: t("settingsForm.couldNotRead", { error: err.message }), type: "error" });
	}
}

async function save() {
	setErrors();
	if (Object.keys(crossErrors.value).length) {
		Object.assign(alert, { text: t("settingsForm.dontGoTogether"), type: "error" });
		notify(t("settingsForm.dontGoTogetherShort"), "error", 6000);
		return;
	}
	const settings = {};
	for (const section of sections.value) {
		for (const setting of section.settings) {
			if (!setting.readonly) {
				settings[setting.key] = values[setting.key];
			}
		}
	}
	saving.value = true;
	try {
		const result = await api.postJson(props.saveUrl, settings);
		const message = serverText(result.message, result.messageCode);
		Object.assign(alert, { text: message, type: "success" });
		notify(message);
		await load();
		emit("saved");
	} catch (err) {
		if (err.status === 400 && err.data?.errors) {
			setErrors(Object.fromEntries(Object.entries(err.data.errors).map(([key, text]) => [key, serverText(text, err.data.errorCodes?.[key])])));
			Object.assign(alert, { text: errors[""] || t("settingsForm.invalid"), type: "error" });
			notify(t("settingsForm.invalidShort"), "error", 6000);
		} else {
			Object.assign(alert, { text: t("common.couldNotSave", { error: err.message }), type: "error" });
			notify(t("common.couldNotSave", { error: err.message }), "error", 6000);
		}
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>

<template>
	<div>
		<v-alert v-if="alert.text" :type="alert.type" variant="tonal" closable class="mb-4" @click:close="alert.text = ''">
			{{ alert.text }}
		</v-alert>
		<v-form @submit.prevent="save">
			<v-card v-for="section in sections" :key="section.name" class="mb-4">
				<v-card-title>{{ sectionTitle(section.name) }}</v-card-title>
				<v-card-text>
					<!-- Each setting with its description underneath, then a gap - so the description reads as belonging to the field above -->
					<div v-for="setting in section.settings" :key="setting.key" class="dl3-setting">
						<v-switch v-if="setting.type === 'bool'" v-model="values[setting.key]" :label="settingLabel(setting.key)"
								  :hint="settingDescription(setting.key)" persistent-hint :error-messages="errorFor(setting.key)"
								  color="primary" density="comfortable" inset></v-switch>

						<v-select v-else-if="setting.choices" v-model="values[setting.key]" :label="settingLabel(setting.key)"
								  :items="setting.choices.map((choice) => ({ title: choiceText(setting.key, choice), value: choice }))" :hint="settingDescription(setting.key)" persistent-hint
								  :error-messages="errorFor(setting.key)" variant="outlined" density="comfortable"></v-select>

						<div v-else-if="setting.type === 'list'">
							<div class="d-flex ga-2">
								<v-text-field v-for="(_, i) in values[setting.key]" :key="i" v-model.number="values[setting.key][i]"
											  :label="t('settingsForm.axis', { label: settingLabel(setting.key), axis: ['X', 'Y', 'Z'][i] ?? i + 1 })" type="number"
											  :error-messages="i === 0 ? errors[setting.key] : undefined" hide-details="auto"
											  variant="outlined" density="comfortable"></v-text-field>
							</div>
							<div class="text-caption text-medium-emphasis mt-1 ms-4">{{ settingDescription(setting.key) }}</div>
						</div>

						<v-text-field v-else-if="setting.type === 'password'" v-model="values[setting.key]" :label="settingLabel(setting.key)"
									  :type="showPassword ? 'text' : 'password'" :hint="settingDescription(setting.key)" persistent-hint
									  :append-inner-icon="showPassword ? mdiEyeOff : mdiEye" @click:append-inner="showPassword = !showPassword"
									  :error-messages="errorFor(setting.key)" variant="outlined" density="comfortable"></v-text-field>

						<!-- inUse: the value in use when it can differ from the saved one (e.g. a blank image_dir) - shown in the empty field -->
						<v-text-field v-else v-model="values[setting.key]" :label="settingLabel(setting.key)"
									  :type="setting.type === 'int' ? 'number' : 'text'" :readonly="setting.readonly"
									  :min="setting.type === 'int' ? limitsFor(setting.key).min : undefined"
									  :max="setting.type === 'int' ? limitsFor(setting.key).max : undefined"
									  :placeholder="setting.inUse || undefined" :persistent-placeholder="!!setting.inUse"
									  :hint="setting.inUse ? t('settingsForm.inUse', { description: settingDescription(setting.key), path: setting.inUse }) : settingDescription(setting.key)" persistent-hint :error-messages="errorFor(setting.key)"
									  variant="outlined" density="comfortable"></v-text-field>
					</div>
				</v-card-text>
				<!-- Every card's Save button saves the whole form, so there is no need to scroll to the bottom -->
				<v-card-actions>
					<v-spacer></v-spacer>
					<v-btn type="submit" :prepend-icon="mdiContentSave" :loading="saving">{{ t("common.save") }}</v-btn>
				</v-card-actions>
			</v-card>
		</v-form>
	</div>
</template>
