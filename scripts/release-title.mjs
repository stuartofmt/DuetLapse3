#!/usr/bin/env node
/**
 * Pick the GitHub Release title for a version: `<tag> — "<title>"`, where <tag> is
 * `vX.Y.Z-dwc<dwcVersion>` (see manifest.mjs).
 *
 * Titles come from scripts/release-titles.txt (one per line); without that file the title is just
 * the tag. The version's position among the semver-sorted `v*` tags with this branch's -dwc suffix
 * is its index into that list (wrapping if it runs out), so each release gets
 * a stable, distinct title with no per-release bookkeeping. The release workflow uses the output as the
 * Release name; run it locally to preview: `node scripts/release-title.mjs [vX.Y.Z]`.
 *
 * A standalone repository (no plugin.json) has the branch being released in brackets after the tag:
 * `vX.Y.Z (main) — "<title>"`.
 *
 * Flags: `--remaining` prints just how many unused titles are left after this one (for low-list checks).
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isStandalone, readManifest, tagSuffix } from "./manifest.mjs";

const here = dirname(fileURLToPath(import.meta.url));

// Warn (here and in the workflow) once this few unused titles remain, so the list gets topped up.
export const LOW_TITLES_THRESHOLD = 5;

function git(args) {
	try {
		return execFileSync("git", args, { encoding: "utf8" }).trim();
	} catch {
		return "";
	}
}

const ver = (v) => v.replace(/^v/, "").trim();

// The DWC suffix of a tag, e.g. "-dwc3.6" in v0.1.0-dwc3.6.
const DWC_SUFFIX = /-dwc\d[0-9A-Za-z.-]*$/;

// semver-ish compare: numeric segment-by-segment; a release (1.0.0) sorts after its prerelease (1.0.0-rc).
function cmp(a, b) {
	const pa = ver(a).split(/[.-]/);
	const pb = ver(b).split(/[.-]/);
	for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
		const x = pa[i] ?? "";
		const y = pb[i] ?? "";
		const nx = /^\d+$/.test(x), ny = /^\d+$/.test(y);
		if (nx && ny) {
			if (+x !== +y) return +x - +y;
		} else if (x !== y) {
			// a present prerelease segment (string) sorts before its absence (the plain release)
			if (x === "") return 1;
			if (y === "") return -1;
			return x < y ? -1 : 1;
		}
	}
	return 0;
}

/**
 * The branch being released (for a standalone release's title): RELEASE_BRANCH if set, else the branch
 * checked out, else - as a tag push checks out the tag, not a branch - the one branch whose tip is this
 * commit (scripts/release.sh pushes the branch, then tags its tip), else the one branch that holds it.
 * "" if that is not clear.
 */
function releaseBranch() {
	if (process.env.RELEASE_BRANCH) return process.env.RELEASE_BRANCH;
	const checkedOut = git(["symbolic-ref", "--quiet", "--short", "HEAD"]);
	if (checkedOut) return checkedOut;
	for (const how of ["--points-at", "--contains"]) {
		const names = new Set(git(["branch", "-r", "--format=%(refname:lstrip=3)", how, "HEAD"])
			.split("\n").map((n) => n.trim()).filter((n) => n && n !== "HEAD"));
		if (names.size === 1) return [...names][0];
		if (names.size > 1) return "";
	}
	return "";
}

/**
 * Resolve the title + list stats for a version (defaults to plugin.json's version; for a standalone
 * repository with no plugin.json, to PLUGIN_VERSION or the tag being released).
 */
export function pickTitle(version) {
	const titlesFile = join(here, "release-titles.txt");
	const titles = (existsSync(titlesFile) ? readFileSync(titlesFile, "utf8") : "")
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l && !l.startsWith("#"));

	const suffix = tagSuffix();
	const fallback = isStandalone() ? process.env.PLUGIN_VERSION || process.env.GITHUB_REF_NAME || "" : readManifest().version;
	const current = ver(version || fallback).replace(DWC_SUFFIX, "");

	// Only this branch's tags: those ending in its -dwc suffix.
	const tags = git(["tag", "-l", "v*"]).split("\n").map((t) => t.trim()).filter(Boolean)
		.filter((t) => (suffix ? t.endsWith(suffix) : !DWC_SUFFIX.test(t)))
		.map((t) => ver(t.slice(0, t.length - suffix.length)));
	if (!tags.includes(current)) tags.push(current);
	tags.sort(cmp);
	const idx = tags.indexOf(current);

	const title = titles.length ? titles[idx % titles.length] : "";
	const branch = isStandalone() ? releaseBranch() : "";
	const tag = `v${current}${suffix}${branch ? ` (${branch})` : ""}`;
	return {
		version: current,
		title,
		label: title ? `${tag} — "${title}"` : tag,
		index: idx,
		total: titles.length,
		remaining: Math.max(0, titles.length - 1 - idx), // unused titles after this one (before wrap)
	};
}

// CLI
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	const args = process.argv.slice(2);
	const remainingOnly = args.includes("--remaining");
	const version = args.find((a) => !a.startsWith("-"));
	const r = pickTitle(version);

	if (remainingOnly) {
		process.stdout.write(String(r.remaining));
	} else {
		if (r.total > 0 && r.remaining <= LOW_TITLES_THRESHOLD) {
			process.stderr.write(
				`⚠️  Only ${r.remaining} unused release title(s) left after this one — add more to scripts/release-titles.txt (it wraps around for now).\n`,
			);
		}
		process.stdout.write(r.label);
	}
}
