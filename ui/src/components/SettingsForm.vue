<!--
	Settings from duetLapse3.json, one card per section, with an input to suit each setting's type.
	Every card's Save button saves the whole form. tab picks the sections (see /api/settings).
-->
<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
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
const configFile = ref("");
const alert = reactive({ text: "", type: "success" });
const saving = ref(false);
const showPassword = ref(false);

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
		configFile.value = data.configFile;
		for (const section of data.sections) {
			for (const setting of section.settings) {
				values[setting.key] = setting.type === "list" ? [...setting.value] : setting.value;
			}
		}
		if (data.error) {
			Object.assign(alert, { text: data.error, type: "error" });
		}
	} catch (err) {
		Object.assign(alert, { text: `Could not read the settings: ${err.message}`, type: "error" });
	}
}

async function save() {
	setErrors();
	if (Object.keys(crossErrors.value).length) {
		Object.assign(alert, { text: "Some settings don't go together (marked in red) - nothing was saved.", type: "error" });
		notify("Some settings don't go together - nothing was saved.", "error", 6000);
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
		Object.assign(alert, { text: result.message, type: "success" });
		notify(result.message);
		await load();
		emit("saved");
	} catch (err) {
		if (err.status === 400 && err.data?.errors) {
			setErrors(err.data.errors);
			const general = err.data.errors[""];
			Object.assign(alert, { text: general || "Some settings are invalid (marked in red) - nothing was saved.", type: "error" });
			notify("Some settings are invalid - nothing was saved.", "error", 6000);
		} else {
			Object.assign(alert, { text: `Could not save: ${err.message}`, type: "error" });
			notify(`Could not save: ${err.message}`, "error", 6000);
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
				<v-card-title>{{ section.name }}</v-card-title>
				<v-card-text>
					<template v-for="setting in section.settings" :key="setting.key">
						<v-switch v-if="setting.type === 'bool'" v-model="values[setting.key]" :label="setting.key"
								  :hint="setting.help" persistent-hint :error-messages="errorFor(setting.key)"
								  color="primary" density="comfortable" inset class="mb-2"></v-switch>

						<v-select v-else-if="setting.choices" v-model="values[setting.key]" :label="setting.key"
								  :items="setting.choices" :hint="setting.help" persistent-hint
								  :error-messages="errorFor(setting.key)" variant="outlined" density="comfortable" class="mb-3"></v-select>

						<div v-else-if="setting.type === 'list'" class="mb-3">
							<div class="d-flex ga-2">
								<v-text-field v-for="(_, i) in values[setting.key]" :key="i" v-model.number="values[setting.key][i]"
											  :label="`${setting.key} ${['X', 'Y', 'Z'][i] ?? i + 1}`" type="number"
											  :error-messages="i === 0 ? errors[setting.key] : undefined" hide-details="auto"
											  variant="outlined" density="comfortable"></v-text-field>
							</div>
							<div class="text-caption text-medium-emphasis mt-1 ms-4">{{ setting.help }}</div>
						</div>

						<v-text-field v-else-if="setting.type === 'password'" v-model="values[setting.key]" :label="setting.key"
									  :type="showPassword ? 'text' : 'password'" :hint="setting.help" persistent-hint
									  :append-inner-icon="showPassword ? mdiEyeOff : mdiEye" @click:append-inner="showPassword = !showPassword"
									  :error-messages="errorFor(setting.key)" variant="outlined" density="comfortable" class="mb-3"></v-text-field>

						<v-text-field v-else v-model="values[setting.key]" :label="setting.key"
									  :type="setting.type === 'int' ? 'number' : 'text'" :readonly="setting.readonly"
									  :min="setting.type === 'int' ? limitsFor(setting.key).min : undefined"
									  :max="setting.type === 'int' ? limitsFor(setting.key).max : undefined"
									  :hint="setting.help" persistent-hint :error-messages="errorFor(setting.key)"
									  variant="outlined" density="comfortable" class="mb-3"></v-text-field>
					</template>
				</v-card-text>
				<!-- Every card's Save button saves the whole form, so there is no need to scroll to the bottom -->
				<v-card-actions>
					<v-spacer></v-spacer>
					<v-btn type="submit" :prepend-icon="mdiContentSave" :loading="saving">Save</v-btn>
				</v-card-actions>
			</v-card>
		</v-form>
		<p class="text-caption text-medium-emphasis">Settings file: {{ configFile }}</p>
	</div>
</template>
