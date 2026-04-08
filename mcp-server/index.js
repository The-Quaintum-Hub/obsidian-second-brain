import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import matter from "gray-matter";
import fs from "fs";
import path from "path";

// ── Vault path ──────────────────────────────────────────────────────────────
const VAULT_PATH = process.env.VAULT_PATH;
if (!VAULT_PATH) {
  console.error("ERROR: VAULT_PATH environment variable is not set.");
  process.exit(1);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Recursively find all .md files in dir, skipping dot-directories. */
function globMd(dir) {
  const results = [];
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return results;
  }
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...globMd(full));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      results.push(full);
    }
  }
  return results;
}

/** Convert absolute path to vault-relative path (no .md extension). */
function toRelPath(absPath) {
  return path.relative(VAULT_PATH, absPath).replace(/\.md$/, "");
}

/** Get file mtime safely. */
function getMtime(absPath) {
  try {
    return fs.statSync(absPath).mtimeMs;
  } catch {
    return 0;
  }
}

// ── MCP Server ───────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "obsidian-wiki",
  version: "1.0.0",
});

// ── Tool 1: wiki_search ──────────────────────────────────────────────────────
server.tool(
  "wiki_search",
  "Search the vault by text query with optional filters. Returns scored results.",
  {
    query: z.string().describe("Text to search for across title, summary, and body"),
    category: z.string().optional().describe("Filter by category folder (e.g. concepts, journal, projects)"),
    project: z.string().optional().describe("Filter by project frontmatter field"),
    tags: z.array(z.string()).optional().describe("Filter by tags (all must match)"),
    limit: z.number().int().min(1).max(100).default(20).describe("Max results to return"),
  },
  async ({ query, category, project, tags, limit }) => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const allFiles = globMd(VAULT_PATH);
    const results = [];

    for (const absPath of allFiles) {
      const rel = toRelPath(absPath);
      const cat = rel.split("/")[0];

      if (category && cat !== category) continue;

      let raw;
      try {
        raw = fs.readFileSync(absPath, "utf8");
      } catch {
        continue;
      }

      const parsed = matter(raw);
      const fm = parsed.data || {};
      const body = parsed.content || "";

      if (project && fm.project !== project) continue;

      if (tags && tags.length > 0) {
        const fileTags = Array.isArray(fm.tags)
          ? fm.tags.map((t) => String(t).toLowerCase())
          : [];
        const allTagsMatch = tags.every((t) => fileTags.includes(t.toLowerCase()));
        if (!allTagsMatch) continue;
      }

      const searchText = [
        String(fm.title || ""),
        String(fm.summary || ""),
        body,
      ]
        .join(" ")
        .toLowerCase();

      let score = 0;
      for (const word of words) {
        const regex = new RegExp(word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g");
        const matches = searchText.match(regex);
        if (matches) score += matches.length;
      }

      if (score === 0 && words.length > 0) continue;

      results.push({
        path: rel,
        title: fm.title || path.basename(rel),
        summary: fm.summary || "",
        project: fm.project || null,
        score,
      });
    }

    results.sort((a, b) => b.score - a.score);
    const top = results.slice(0, limit);

    return {
      content: [{ type: "text", text: JSON.stringify(top, null, 2) }],
    };
  }
);

// ── Tool 2: wiki_get_page ────────────────────────────────────────────────────
server.tool(
  "wiki_get_page",
  "Read a specific vault page by relative path (e.g. 'concepts/rls-policies'). Returns full file content.",
  {
    path: z.string().describe("Vault-relative path to the page (with or without .md extension)"),
  },
  async ({ path: relPath }) => {
    const normalised = relPath.replace(/\.md$/, "");
    const absPath = path.join(VAULT_PATH, normalised + ".md");

    let content;
    try {
      content = fs.readFileSync(absPath, "utf8");
    } catch {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ error: `Page not found: ${relPath}` }, null, 2),
          },
        ],
      };
    }

    return {
      content: [{ type: "text", text: content }],
    };
  }
);

// ── Tool 3: wiki_list_sessions ───────────────────────────────────────────────
server.tool(
  "wiki_list_sessions",
  "List session notes from journal/ with optional filters. Returns sorted by date descending.",
  {
    project: z.string().optional().describe("Filter by project"),
    date_from: z.string().optional().describe("ISO date lower bound inclusive (e.g. '2025-01-01')"),
    date_to: z.string().optional().describe("ISO date upper bound inclusive (e.g. '2025-12-31')"),
    limit: z.number().int().min(1).max(200).default(50).describe("Max results"),
  },
  async ({ project, date_from, date_to, limit }) => {
    const journalDir = path.join(VAULT_PATH, "journal");
    const files = globMd(journalDir);
    const sessions = [];

    for (const absPath of files) {
      let raw;
      try {
        raw = fs.readFileSync(absPath, "utf8");
      } catch {
        continue;
      }

      const fm = matter(raw).data || {};

      if (project && fm.project !== project) continue;

      const noteDate = fm.date ? String(fm.date).slice(0, 10) : null;
      if (date_from && noteDate && noteDate < date_from) continue;
      if (date_to && noteDate && noteDate > date_to) continue;

      sessions.push({
        path: toRelPath(absPath),
        title: fm.title || path.basename(toRelPath(absPath)),
        date: noteDate,
        project: fm.project || null,
        summary: fm.summary || "",
        tags: fm.tags || [],
      });
    }

    sessions.sort((a, b) => {
      if (!a.date && !b.date) return 0;
      if (!a.date) return 1;
      if (!b.date) return -1;
      return b.date.localeCompare(a.date);
    });

    return {
      content: [{ type: "text", text: JSON.stringify(sessions.slice(0, limit), null, 2) }],
    };
  }
);

// ── Tool 4: wiki_get_links ───────────────────────────────────────────────────
server.tool(
  "wiki_get_links",
  "Get incoming and outgoing [[wikilinks]] for a vault page.",
  {
    path: z.string().describe("Vault-relative path (e.g. 'concepts/rls-policies')"),
  },
  async ({ path: relPath }) => {
    const normalised = relPath.replace(/\.md$/, "");
    const absPath = path.join(VAULT_PATH, normalised + ".md");

    let content;
    try {
      content = fs.readFileSync(absPath, "utf8");
    } catch {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ error: `Page not found: ${relPath}` }, null, 2),
          },
        ],
      };
    }

    // Outgoing: [[Target]] or [[Target|Alias]]
    const outgoingSet = new Set();
    const wikilinkRe = /\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g;
    let match;
    while ((match = wikilinkRe.exec(content)) !== null) {
      outgoingSet.add(match[1].trim());
    }
    const outgoing = Array.from(outgoingSet);

    // Incoming: scan all files for [[targetBasename
    const targetName = path.basename(normalised);
    const incoming = [];
    const allFiles = globMd(VAULT_PATH);

    for (const candidateAbs of allFiles) {
      if (candidateAbs === absPath) continue;
      let candidateContent;
      try {
        candidateContent = fs.readFileSync(candidateAbs, "utf8");
      } catch {
        continue;
      }
      if (candidateContent.toLowerCase().includes("[[" + targetName.toLowerCase())) {
        incoming.push(toRelPath(candidateAbs));
      }
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ path: normalised, outgoing, incoming }, null, 2),
        },
      ],
    };
  }
);

// ── Tool 5: wiki_recent ──────────────────────────────────────────────────────
server.tool(
  "wiki_recent",
  "Get N most recent session notes by file modification time.",
  {
    n: z.number().int().min(1).max(100).default(10).describe("Number of recent sessions to return"),
  },
  async ({ n }) => {
    const journalDir = path.join(VAULT_PATH, "journal");
    const files = globMd(journalDir);

    const withMtime = files.map((absPath) => ({
      absPath,
      mtime: getMtime(absPath),
    }));

    withMtime.sort((a, b) => b.mtime - a.mtime);

    const recent = [];
    for (const { absPath, mtime } of withMtime.slice(0, n)) {
      let raw;
      try {
        raw = fs.readFileSync(absPath, "utf8");
      } catch {
        continue;
      }
      const fm = matter(raw).data || {};
      recent.push({
        path: toRelPath(absPath),
        title: fm.title || path.basename(toRelPath(absPath)),
        date: fm.date ? String(fm.date).slice(0, 10) : null,
        project: fm.project || null,
        summary: fm.summary || "",
        modified_at: new Date(mtime).toISOString(),
      });
    }

    return {
      content: [{ type: "text", text: JSON.stringify(recent, null, 2) }],
    };
  }
);

// ── Tool 6: wiki_stats ───────────────────────────────────────────────────────
server.tool(
  "wiki_stats",
  "Vault statistics: total pages, sessions count, projects list, categories breakdown, last ingestion.",
  {},
  async () => {
    const allFiles = globMd(VAULT_PATH);
    const categories = {};
    const projectSet = new Set();
    let totalPages = 0;
    let sessions = 0;

    for (const absPath of allFiles) {
      totalPages++;
      const rel = toRelPath(absPath);
      const cat = rel.split("/")[0];
      categories[cat] = (categories[cat] || 0) + 1;
      if (cat === "journal") sessions++;

      try {
        const raw = fs.readFileSync(absPath, "utf8");
        const fm = matter(raw).data || {};
        if (fm.project) projectSet.add(String(fm.project));
      } catch {
        // skip unreadable files
      }
    }

    const manifestPath = path.join(VAULT_PATH, "_meta", ".manifest.json");
    let lastIngestion = null;
    let manifestStats = null;
    try {
      const manifestRaw = fs.readFileSync(manifestPath, "utf8");
      const manifest = JSON.parse(manifestRaw);
      lastIngestion = manifest.last_updated || null;
      manifestStats = manifest.stats || null;
    } catch {
      // manifest may not exist yet
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              total_pages: totalPages,
              sessions_count: sessions,
              projects: Array.from(projectSet).sort(),
              categories,
              last_ingestion: lastIngestion,
              manifest_stats: manifestStats,
            },
            null,
            2
          ),
        },
      ],
    };
  }
);

// ── Start ─────────────────────────────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
