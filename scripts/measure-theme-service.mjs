#!/usr/bin/env node

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i].startsWith('--')) args.set(process.argv[i].slice(2), process.argv[i + 1]);
}

const baseUrl = args.get('base-url') || process.env.THEME_SERVICE_URL;
const endpoint = args.get('endpoint') || process.env.THEME_SERVICE_ENDPOINT || '/';
const vus = Number(args.get('vus') || process.env.THEME_SERVICE_VUS || 20);
const durationSeconds = Number(args.get('duration') || process.env.THEME_SERVICE_DURATION || 30);
const maxP95 = Number(args.get('max-p95-ms') || process.env.THEME_SERVICE_MAX_P95_MS || 500);
const maxP99 = Number(args.get('max-p99-ms') || process.env.THEME_SERVICE_MAX_P99_MS || 1000);
const maxErrorRate = Number(args.get('max-error-rate') || process.env.THEME_SERVICE_MAX_ERROR_RATE || 0.01);

if (!baseUrl) throw new Error('Missing --base-url or THEME_SERVICE_URL');
if (!Number.isInteger(vus) || vus < 1) throw new Error('vus must be a positive integer');
if (!Number.isInteger(durationSeconds) || durationSeconds < 1) throw new Error('duration must be a positive integer');

const url = new URL(endpoint, baseUrl).toString();
const endAt = Date.now() + durationSeconds * 1000;
const latencies = [];
let requests = 0;
let errors = 0;

async function worker() {
  while (Date.now() < endAt) {
    const started = performance.now();
    try {
      const response = await fetch(url, { headers: { accept: 'application/json' } });
      if (!response.ok) errors += 1;
      await response.arrayBuffer();
    } catch {
      errors += 1;
    } finally {
      requests += 1;
      latencies.push(performance.now() - started);
    }
  }
}

await Promise.all(Array.from({ length: vus }, worker));
latencies.sort((a, b) => a - b);
const percentile = (p) => latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * p) - 1)] || 0;
const result = {
  url,
  vus,
  durationSeconds,
  requests,
  errors,
  errorRate: requests ? errors / requests : 1,
  p95Ms: Number(percentile(0.95).toFixed(2)),
  p99Ms: Number(percentile(0.99).toFixed(2)),
  thresholds: { maxP95Ms: maxP95, maxP99Ms: maxP99, maxErrorRate },
};
console.log(JSON.stringify(result, null, 2));

if (result.p95Ms > maxP95 || result.p99Ms > maxP99 || result.errorRate > maxErrorRate) {
  process.exitCode = 1;
}
