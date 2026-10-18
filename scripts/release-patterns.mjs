/**
 * Exclude patterns (a subset of .gitignore, described in scripts/release-exclude.txt), shared by
 * ./prune-release.mjs (the release ZIP) and ./release-standalone.mjs (the standalone ZIP).
 */
import { existsSync, lstatSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { join, relative } from "node:path";

/** A pattern as a rule whose regular expression is matched against paths relative to the folder walked. */
export function compile(pattern) {
	let p = pattern.replace(/^\/+/, "");
	const dirOnly = p.endsWith("/");
	p = p.replace(/\/+$/, "");
	const anywhere = !p.includes("/");   // no "/" inside: the name matches at any depth
	let re = "";
	for (let i = 0; i < p.length; i++) {
		const c = p[i];
		if (p.startsWith("**/", i)) { re += "(?:[^/]+/)*"; i += 2; }
		else if (p.startsWith("**", i)) { re += ".*"; i += 1; }
		else if (c === "*") re += "[^/]*";
		else if (c === "?") re += "[^/]";
		else re += c.replace(/[.+^${}()|[\]\\]/g, "\\$&");
	}
	return { pattern, dirOnly, regex: new RegExp(anywhere ? `(^|/)${re}$` : `^${re}$`), matched: 0 };
}

/** The patterns in a file: one per line, blank lines and lines starting with # ignored. None if it is missing. */
export function readPatterns(file) {
	if (!existsSync(file)) return [];
	return readFileSync(file, "utf8").split(/\r?\n/)
		.map((line) => line.trim())
		.filter((line) => line && !line.startsWith("#"));
}

/**
 * The files and folders in dir that a rule matches, as { full, rel } (rel ends in / for a folder). A matching
 * folder is taken whole and not looked inside. Each rule's matched count is increased for what it matched.
 */
export function findMatches(dir, rules) {
	const found = [];
	(function walk(current) {
		for (const entry of readdirSync(current, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
			const full = join(current, entry.name);
			const rel = relative(dir, full).split("\\").join("/");
			const isDir = entry.isDirectory() && !lstatSync(full).isSymbolicLink();
			const rule = rules.find((r) => (!r.dirOnly || isDir) && r.regex.test(rel));
			if (rule) {
				rule.matched++;
				found.push({ full, rel: isDir ? `${rel}/` : rel });
			} else if (isDir) {
				walk(full);
			}
		}
	})(dir);
	return found;
}

/** Delete what findMatches found. */
export function removeMatches(found) {
	for (const { full } of found) rmSync(full, { recursive: true, force: true });
}
