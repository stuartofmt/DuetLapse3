/**
 * Locate and read the plugin's plugin.json, so the release scripts need no per-plugin changes.
 *
 * Search order (the same as the release workflow and scripts/release.sh):
 *   1. MANIFEST, if set (path relative to the repository root; the release workflow sets it)
 *   2. plugin.json at the repository root
 *   3. the shallowest plugin.json in a subfolder (alphabetical within a depth), skipping .git,
 *      node_modules and venv
 *
 * A repository with no plugin.json at all is not a plugin: it is released only as a standalone ZIP, which
 * needs a standalone/ folder (see isStandalone, hasStandaloneBuild and standaloneSource).
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

export const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

const SKIP = new Set([".git", "node_modules", "venv"]);

function findManifests(directory, depth = 0, found = []) {
	for (const entry of readdirSync(directory, { withFileTypes: true })) {
		const full = join(directory, entry.name);
		if (entry.isDirectory() && !SKIP.has(entry.name)) findManifests(full, depth + 1, found);
		else if (entry.isFile() && entry.name === "plugin.json") found.push({ path: full, depth });
	}
	return found;
}

/** Path of plugin.json relative to the repository root, or "" if the repository has none. */
export function findManifestPath() {
	if (process.env.MANIFEST) return process.env.MANIFEST;
	if (existsSync(join(repoRoot, "plugin.json"))) return "plugin.json";
	const found = findManifests(repoRoot)
		.sort((a, b) => a.depth - b.depth || a.path.localeCompare(b.path));
	return found.length ? relative(repoRoot, found[0].path) : "";
}

/** Path of plugin.json relative to the repository root, e.g. "plugin.json" or "Code/plugin.json". */
export function manifestPath() {
	const path = findManifestPath();
	if (!path) throw new Error(`No plugin.json found in ${repoRoot}`);
	return path;
}

/** Whether the repository has no plugin.json: it is not a plugin, so it is released only as a standalone ZIP. */
export function isStandalone() {
	return !findManifestPath();
}

/**
 * The name of a repository with no plugin.json (its standalone ZIP is <name>-<version>.zip): the repository's
 * name - from GitHub Actions' GITHUB_REPOSITORY, else the git remote "origin", else the repository folder's name.
 */
export function standaloneName() {
	const fromRepo = process.env.GITHUB_REPOSITORY?.split("/")[1];
	if (fromRepo) return fromRepo;
	try {
		const url = execFileSync("git", ["-C", repoRoot, "remote", "get-url", "origin"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
		const name = basename(url).replace(/\.git$/, "");
		if (name) return name;
	} catch {
		// no git, or no origin remote
	}
	return basename(repoRoot);
}

/**
 * The standalone/ folder at the top of the repository is what makes a standalone ZIP (see
 * ./release-standalone.mjs). Prep_and_Package's Prepare makes it with "Create standalone" ticked.
 */
export const STANDALONE_DIR = "standalone";

/** Whether a standalone ZIP is released: the repository has a standalone/ folder at its top. */
export function hasStandaloneBuild() {
	const dir = join(repoRoot, STANDALONE_DIR);
	return existsSync(dir) && statSync(dir).isDirectory();
}

/**
 * The folder the standalone ZIP is made from, relative to the repository root ("." for the root): the first
 * line of standalone/source.txt (written by Prepare: the project folder), else the folder holding plugin.json,
 * else the repository root. Throws if it is not a folder inside the repository.
 */
export function standaloneSource() {
	const file = join(repoRoot, STANDALONE_DIR, "source.txt");
	let rel = existsSync(file)
		? readFileSync(file, "utf8").split(/\r?\n/).map((l) => l.replace(/#.*/, "").trim()).find(Boolean)
		: undefined;
	if (rel === undefined) rel = isStandalone() ? "." : dirname(manifestPath());
	rel = rel.replace(/\\/g, "/").replace(/^\.\/+/, "").replace(/\/+$/, "") || ".";
	const full = join(repoRoot, rel);
	if (rel.split("/").includes("..") || !existsSync(full) || !statSync(full).isDirectory()) {
		throw new Error(`${STANDALONE_DIR}/source.txt names "${rel}", which is not a folder in the repository.`);
	}
	return rel;
}

/**
 * The standalone ZIP's file name. A plugin's: standalone-<id>-<version>.zip, next to its plugin ZIP. A repository
 * with no plugin.json has only this ZIP: <name>-<version>.zip.
 */
export function standaloneZipName(version, manifest = isStandalone() ? null : readManifest()) {
	return manifest ? `standalone-${manifest.id}-${version ?? manifest.version}.zip` : `${standaloneName()}-${version}.zip`;
}

/**
 * The version of a repository with no plugin.json: PLUGIN_VERSION (the release workflow sets it from the tag),
 * else the newest v* tag, else "dev".
 */
export function standaloneVersion() {
	if (process.env.PLUGIN_VERSION) return process.env.PLUGIN_VERSION;
	try {
		const tag = execFileSync("git", ["-C", repoRoot, "describe", "--tags", "--abbrev=0", "--match", "v*"],
			{ encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
		if (tag) return tag.replace(/^v/, "");
	} catch {
		// no git, or no v* tag
	}
	return "dev";
}

/** The parsed plugin.json. */
export function readManifest() {
	return JSON.parse(readFileSync(join(repoRoot, manifestPath()), "utf8"));
}

/**
 * This branch's release channel, from scripts/release-channel.txt (default "latest"):
 *   latest      - the main line. Its Releases are marked Latest.
 *   maintenance - a line built for an older DWC. Its Releases are never marked Latest.
 * Tags are v<version>-dwc<dwcVersion> on both channels (see tagSuffix), or v<version> for a plugin with
 * no dwcVersion.
 */
export function releaseChannel() {
	const file = join(repoRoot, "scripts", "release-channel.txt");
	const channel = existsSync(file)
		? readFileSync(file, "utf8").split("\n").map((l) => l.replace(/#.*/, "").trim()).find(Boolean)
		: undefined;
	if (channel && !["latest", "maintenance"].includes(channel)) {
		throw new Error(`scripts/release-channel.txt must say "latest" or "maintenance", not "${channel}".`);
	}
	return channel || "latest";
}

/**
 * Whether the plugin is built with DWC's plugin builder: plugin.json has a dwcVersion (it has a DWC
 * interface to compile). Without one the plugin is simply zipped, as plugin_tools does. Never for a
 * standalone repository (no plugin.json, so manifest is null).
 */
export function needsDwcBuild(manifest = isStandalone() ? null : readManifest()) {
	const value = manifest?.dwcVersion;
	return value !== undefined && value !== null && String(value).trim() !== "";
}

/**
 * The suffix after v<version> in release tags: "-dwc<dwcVersion>", e.g. "-dwc3.7". Every tag carries
 * the DWC version it is built for, so branches for different DWC versions never clash. A plugin with
 * no dwcVersion (or a standalone repository) is not tied to a DWC version, so its tags have no suffix ("").
 */
export function tagSuffix(manifest = isStandalone() ? null : readManifest()) {
	return needsDwcBuild(manifest) ? `-dwc${manifest.dwcVersion}` : "";
}
