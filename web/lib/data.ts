import fs from 'node:fs';
import path from 'node:path';

import {Deal} from './shared';

const repoRoot = path.join(process.cwd(), '..');
const dealsDir = path.join(repoRoot, 'data', 'deals');
const guidesDir = path.join(repoRoot, 'data', 'guides');

export function getLatestDeals(): Deal[] {
  if (!fs.existsSync(dealsDir)) return [];
  const files = fs.readdirSync(dealsDir).filter((file) => file.endsWith('.json')).sort().reverse();
  if (files.length === 0) return [];
  const raw = fs.readFileSync(path.join(dealsDir, files[0]), 'utf-8');
  return JSON.parse(raw) as Deal[];
}

export function getDeal(id: string): Deal | undefined {
  return getLatestDeals().find((deal) => deal.id === id);
}

export function getGuides(): string[] {
  if (!fs.existsSync(guidesDir)) return [];
  return fs.readdirSync(guidesDir).filter((file) => file.endsWith('.md'));
}

export function getGuideMarkdown(id: string): string {
  const target = path.join(guidesDir, `${id}.md`);
  if (!fs.existsSync(target)) return '# 攻略生成中\n\n这条 deal 暂时还没有本地攻略。';
  return fs.readFileSync(target, 'utf-8');
}
