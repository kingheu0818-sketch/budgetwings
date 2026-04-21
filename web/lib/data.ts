import fs from 'node:fs';
import path from 'node:path';

import {
  type Deal,
  type DisplayDeal,
  type EvalReport,
  type StatusSnapshot,
  buildFallbackGuide,
  looksCorrupted,
  normalizeDeal,
  normalizeText,
} from './shared';

const repoRoot = path.join(process.cwd(), '..');
const dealsDir = path.join(repoRoot, 'data', 'deals');
const guidesDir = path.join(repoRoot, 'data', 'guides');
const reportsDir = path.join(repoRoot, 'eval', 'reports');
const tracesDir = path.join(repoRoot, 'data', 'traces');
const databasePath = path.join(repoRoot, 'data', 'budgetwings.db');

export function getLatestDeals(): DisplayDeal[] {
  const rawDeals = readLatestJsonArray<Deal>(dealsDir);
  return rawDeals.map(normalizeDeal);
}

export function getDeal(id: string): DisplayDeal | undefined {
  return getLatestDeals().find((deal) => deal.id === id);
}

export function getGuideIds(): string[] {
  if (!fs.existsSync(guidesDir)) return [];
  return fs
    .readdirSync(guidesDir)
    .filter((file) => file.endsWith('.md'))
    .map((file) => file.replace(/\.md$/, ''));
}

export function getGuideMarkdown(id: string): string {
  const deal = getDeal(id);
  const target = path.join(guidesDir, `${id}.md`);
  const fallback = deal
    ? buildFallbackGuide(deal)
    : '# 攻略暂未生成\n\n这条路线还没有可展示的本地攻略。';

  if (!fs.existsSync(target)) {
    return fallback;
  }

  const markdown = fs.readFileSync(target, 'utf-8');
  if (looksCorrupted(markdown)) {
    return fallback;
  }
  return normalizeText(markdown);
}

export function getLatestEvalReport(): EvalReport | null {
  const report = readLatestJson<EvalReport>(reportsDir);
  if (!report) return null;
  return {
    ...report,
    metadata: {
      ...report.metadata,
      cities: report.metadata.cities.map(normalizeText),
      source_mode: normalizeText(report.metadata.source_mode),
    },
  };
}

export function getStatusSnapshot(): StatusSnapshot {
  const latestDeals = getLatestFile(dealsDir, '.json');
  const latestEval = getLatestFile(reportsDir, '.json');
  const latestTrace = getLatestFile(tracesDir, '.json');

  return {
    latestDealsFile: latestDeals?.name ?? null,
    latestDealsUpdatedAt: latestDeals?.updatedAt ?? null,
    latestEvalFile: latestEval?.name ?? null,
    latestEvalUpdatedAt: latestEval?.updatedAt ?? null,
    latestTraceFile: latestTrace?.name ?? null,
    latestTraceUpdatedAt: latestTrace?.updatedAt ?? null,
    dealsCount: getLatestDeals().length,
    guidesCount: getGuideIds().length,
    hasDatabase: fs.existsSync(databasePath),
  };
}

function readLatestJsonArray<T>(dir: string): T[] {
  const payload = readLatestJson<T[]>(dir);
  return Array.isArray(payload) ? payload : [];
}

function readLatestJson<T>(dir: string): T | null {
  const latest = getLatestFile(dir, '.json');
  if (!latest) return null;
  const raw = fs.readFileSync(latest.path, 'utf-8');
  return JSON.parse(raw) as T;
}

function getLatestFile(
  dir: string,
  ext: string
): {name: string; path: string; updatedAt: string} | null {
  if (!fs.existsSync(dir)) return null;
  const files = fs
    .readdirSync(dir)
    .filter((file) => file.endsWith(ext))
    .sort()
    .reverse();
  if (files.length === 0) return null;

  const file = files[0];
  const filePath = path.join(dir, file);
  const stat = fs.statSync(filePath);

  return {
    name: file,
    path: filePath,
    updatedAt: stat.mtime.toISOString(),
  };
}
