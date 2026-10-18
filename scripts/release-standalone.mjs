#!/usr/bin/env node
/**
 * Build the standalone ZIP: the program packaged to run on its own (e.g. with the run.sh / run.bat launchers that
 * Prep_and_Package's Prepare puts in standalone/), without DWC.
 *
 * Trigger: a standalone/ folder at the top of the repository (see hasStandaloneBuild in ./manifest.mjs) - Prepare
 * makes it when "Create standalone" is ticked. The release workflow then builds this ZIP and attaches it to the
 * Release: next to the plugin ZIP for a plugin, or as the only ZIP for a repository with no plugin.json. It can be
 * run locally in the same way to try the ZIP out.
 *
 * The ZIP is made from:
 *   1. the source folder - standalone/source.txt (the project folder, written by Prepare), else the folder holding
 *      plugin.json, else the repository root - without __pycache__/, venv/, .git/, *.pyc, *.log, node_modules/
 *      and what scripts/release-exclude.txt lists. From the repository root, the release workflow's own files
 *      (.github/, its scripts) and the standalone/ folder are left out too;
 *   2. without what standalone/exclude.txt lists as well (same pattern rules, relative to the source folder),
 *      e.g. a plugin's plugin.json and sd/ files;
 *   3. plus everything in standalone/ (e.g. run.sh, run.bat, a README), added at the top of the ZIP and replacing
 *      a file of the same name - except source.txt, exclude.txt, .gitignore and ZIP files.
 * Folders left empty are dropped. The ZIP - standalone-<id>-<version>.zip for a plugin, <name>-<version>.zip for a
 * repository with no plugin.json - is written to standalone/ (ZIP files already there are removed first): it is a
 * build output, so add standalone/*.zip to .gitignore.
 *
 * Usage:
 *   node scripts/release-standalone.mjs           build the ZIP
 *   node scripts/release-standalone.mjs --list    show what would go in it - changes nothing
 */
import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import {
	hasStandaloneBuild, isStandalone, readManifest, repoRoot, STANDALONE_DIR, standaloneSource, standaloneVersion,
	standaloneZipName,
} from "./manifest.mjs";
import { compile, findMatches, readPatterns, removeMatches } from "./release-patterns.mjs";

const ALWAYS = ["__pycache__/", "venv/", ".git/", "*.pyc", "*.log", "node_modules/"];
// From the repository root: the release workflow itself (as the plugin ZIP leaves it out of a repository-root plugin
// via scripts/release-exclude.txt)
const ROOT_ALWAYS = [".github/", "scripts/manifest.mjs", "scripts/prune-release.mjs", "scripts/release-*.mjs",
	"scripts/release-*.txt", "scripts/release.sh"];
// In standalone/ but not copied into the ZIP
const NOT_COPIED = new Set(["source.txt", "exclude.txt", ".gitignore"]);

const list = process.argv.includes("--list");
if (process.argv.slice(2).some((a) => a !== "--list")) {
	console.error("Usage: node scripts/release-standalone.mjs [--list]");
	process.exit(2);
}
if (!hasStandaloneBuild()) {
	console.log(`No ${STANDALONE_DIR}/ folder - there is no standalone ZIP to build.`);
	process.exit(0);
}

const standaloneDir = join(repoRoot, STANDALONE_DIR);
const sourceRel = standaloneSource();
const sourceDir = join(repoRoot, sourceRel);
const zipName = isStandalone() ? standaloneZipName(standaloneVersion()) : standaloneZipName(readManifest().version);

const stage = mkdtempSync(join(tmpdir(), "standalone-"));
let exitCode;
try {
	exitCode = build();
} finally {
	rmSync(stage, { recursive: true, force: true });
}
process.exit(exitCode);

function build() {
	console.log(`Source folder: ${sourceRel}`);
	// 1-2. A copy of the source folder, without what is always left out, release-exclude.txt and standalone/exclude.txt
	cpSync(sourceDir, stage, {
		recursive: true,
		// Never the standalone/ folder itself (when the source is the repository root) or the big leftovers
		filter: (src) => src === sourceDir
			|| (src !== standaloneDir && ![".git", "venv", "__pycache__", "node_modules"].includes(src.split(/[\\/]/).pop())),
	});
	const always = [...ALWAYS, ...(sourceRel === "." ? ROOT_ALWAYS : [])].map(compile);
	const own = readPatterns(join(repoRoot, "scripts", "release-exclude.txt")).map(compile);
	const extra = readPatterns(join(standaloneDir, "exclude.txt")).map(compile);
	removeMatches(findMatches(stage, [...always, ...own]));
	const left = findMatches(stage, extra);
	removeMatches(left);
	for (const { rel } of left) console.log(`left out (${STANDALONE_DIR}/exclude.txt): ${rel}`);
	for (const rule of extra.filter((r) => !r.matched)) {
		console.log(`::warning::${STANDALONE_DIR}/exclude.txt: "${rule.pattern}" matched nothing in ${sourceRel}`);
	}

	// 3. The standalone files on top
	for (const entry of readdirSync(standaloneDir)) {
		if (NOT_COPIED.has(entry) || /\.zip$/i.test(entry)) continue;
		cpSync(join(standaloneDir, entry), join(stage, entry), { recursive: true, force: true });
	}
	dropEmptyFolders(stage);

	const files = listFiles(stage);
	if (!files.length) {
		console.error("::error::Nothing to put in the standalone ZIP: every file was left out.");
		return 1;
	}
	if (list) {
		console.log(`${zipName} would contain:`);
		for (const file of files) console.log(`  ${file}`);
		return 0;
	}

	for (const old of readdirSync(standaloneDir).filter((n) => /\.zip$/i.test(n))) {
		rmSync(join(standaloneDir, old));
	}
	const zipPath = join(standaloneDir, zipName);
	makeZip(stage, zipPath);
	console.log(`Built ${relative(repoRoot, zipPath)} (${files.length} files)`);
	return 0;
}

function dropEmptyFolders(dir) {
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		if (entry.isDirectory()) dropEmptyFolders(join(dir, entry.name));
	}
	if (dir !== stage && readdirSync(dir).length === 0) rmSync(dir, { recursive: true });
}

function listFiles(dir) {
	const out = [];
	(function walk(current) {
		for (const entry of readdirSync(current, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
			const full = join(current, entry.name);
			if (entry.isDirectory()) walk(full);
			else out.push(relative(dir, full).split("\\").join("/"));
		}
	})(dir);
	return out;
}

// zip keeps file permissions (e.g. an executable run.sh). Where there is no zip (e.g. Git Bash on Windows),
// Python's zipfile does the same.
function makeZip(dir, zipPath) {
	try {
		execFileSync("zip", ["-r", "-X", "-q", zipPath, "."], { cwd: dir, stdio: ["ignore", "inherit", "inherit"] });
		return;
	} catch (error) {
		if (error.code !== "ENOENT") throw error;
	}
	const script = "import os,sys,zipfile\n"
		+ "src,out=sys.argv[1],sys.argv[2]\n"
		+ "with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:\n"
		+ " for root,dirs,names in os.walk(src):\n"
		+ "  dirs.sort()\n"
		+ "  for n in sorted(names):\n"
		+ "   p=os.path.join(root,n); z.write(p,os.path.relpath(p,src))\n";
	for (const python of ["python3", "python", "py"]) {
		try {
			execFileSync(python, ["-c", script, dir, zipPath], { stdio: ["ignore", "inherit", "inherit"] });
			return;
		} catch (error) {
			if (error.code !== "ENOENT") throw error;
		}
	}
	throw new Error("Neither zip nor Python was found to make the ZIP.");
}
