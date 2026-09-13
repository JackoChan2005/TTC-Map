import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export async function launchBrowser() {
  process.chdir(fileURLToPath(new URL('../../', import.meta.url)));
  const { chromium } = process.env.PLAYWRIGHT_MODULE
    ? await import(pathToFileURL(path.resolve(process.env.PLAYWRIGHT_MODULE)))
    : await import('playwright');
  return chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {})
  });
}
