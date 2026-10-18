<!-- Config, Execution and Files tabs: the settings in the sections tab picks (see /api/settings) -->
<script setup>
import SettingsForm from "../components/SettingsForm.vue";
import { t } from "../i18n.js";

defineProps({ tab: { type: String, default: "config" } });  // config, execution or files
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-alert type="info" variant="tonal" density="compact" class="mb-4">
				{{ t("config.restartNeeded") }}
			</v-alert>
			<SettingsForm :tab="tab" save-url="/config/save"></SettingsForm>
		</v-col>
	</v-row>
</template>
