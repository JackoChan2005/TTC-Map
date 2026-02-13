const fs = require('fs/promises');
const http = require('http');
const https = require('https');
const path = require('path');

const BASE_DIR = path.resolve(__dirname, '..', '..');
const DEFAULT_CKAN_BASE_URL = 'https://ckan0.cf.opendata.inter.prod-toronto.ca';
const CKAN_SOURCE_PREFIX = 'ckan-package:';
const isLikelyJsonUrl = (url) => /\.json($|\?)/i.test(url) || /format=json/i.test(url);

const isHttpSource = (value) => /^https?:\/\//i.test(value);

const fetchJsonFromHttp = (url) => new Promise((resolve, reject) => {
  const protocol = url.startsWith('https://') ? https : http;

  protocol
    .get(url, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        reject(new Error(`Failed to fetch JSON from ${url}. HTTP ${res.statusCode}`));
        return;
      }

      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (err) {
          reject(new Error(`Invalid JSON from ${url}: ${err.message}`));
        }
      });
    })
    .on('error', reject);
});

const fetchJsonFromHttps = (url) => new Promise((resolve, reject) => {
  https
    .get(url, (res) => {
      if (res.statusCode && res.statusCode >= 400) {
        reject(new Error(`Failed to fetch JSON from ${url}. HTTP ${res.statusCode}`));
        return;
      }

      const chunks = [];
      res.on('data', (chunk) => {
        chunks.push(chunk);
      });
      res.on('end', () => {
        try {
          const payload = Buffer.concat(chunks).toString();
          resolve(JSON.parse(payload));
        } catch (err) {
          reject(new Error(`Invalid JSON from ${url}: ${err.message}`));
        }
      });
      res.on('error', reject);
    })
    .on('error', reject);
});

const fetchJsonFromFile = async (sourcePath) => {
  const resolvedPath = path.isAbsolute(sourcePath)
    ? sourcePath
    : path.resolve(BASE_DIR, sourcePath);

  const content = await fs.readFile(resolvedPath, 'utf8');
  return JSON.parse(content);
};

const getPackageMetadata = async (packageId, ckanBaseUrl = DEFAULT_CKAN_BASE_URL) => {
  const apiUrl = `${ckanBaseUrl}/api/3/action/package_show?id=${packageId}`;
  const response = await fetchJsonFromHttps(apiUrl);

  if (!response || response.success !== true || !response.result) {
    throw new Error(`Unexpected CKAN package_show response for package ${packageId}`);
  }

  return response.result;
};

const pickResource = (pkg) => {
  if (!pkg || !Array.isArray(pkg.resources) || pkg.resources.length === 0) {
    return null;
  }

  const preferredId = process.env.CKAN_RESOURCE_ID;
  const preferredName = process.env.CKAN_RESOURCE_NAME;

  if (preferredId) {
    const byId = pkg.resources.find((resource) => resource.id === preferredId);
    if (byId) {
      return byId;
    }
  }

  if (preferredName) {
    const normalized = preferredName.toLowerCase();
    const byName = pkg.resources.find((resource) =>
      String(resource.name || '').toLowerCase().includes(normalized)
    );
    if (byName) {
      return byName;
    }
  }

  const jsonFormat = pkg.resources.find((resource) =>
    String(resource.format || '').toLowerCase() === 'json'
  );
  if (jsonFormat) {
    return jsonFormat;
  }

  const jsonUrl = pkg.resources.find((resource) =>
    String(resource.url || '').toLowerCase().endsWith('.json')
  );
  if (jsonUrl) {
    return jsonUrl;
  }

  const datastore = pkg.resources.find((resource) => resource.datastore_active);
  if (datastore) {
    return datastore;
  }

  return pkg.resources[0];
};

const fetchFromCkanPackage = async (packageId, ckanBaseUrl = DEFAULT_CKAN_BASE_URL) => {
  const pkg = await getPackageMetadata(packageId, ckanBaseUrl);
  const shouldFetchResource = String(process.env.CKAN_FETCH_RESOURCE || 'false').toLowerCase() === 'true';

  if (!shouldFetchResource) {
    return pkg;
  }

  const resource = pickResource(pkg);

  if (!resource) {
    throw new Error(`No resources found for CKAN package ${packageId}`);
  }

  if (resource.url && /^https?:\/\//i.test(resource.url) && isLikelyJsonUrl(resource.url)) {
    return fetchJsonFromHttp(resource.url);
  }

  if (resource.datastore_active && resource.id) {
    const datastoreUrl = `${ckanBaseUrl}/api/3/action/datastore_search?resource_id=${resource.id}&limit=${Number(process.env.CKAN_DATASTORE_LIMIT || 1000)}`;
    const response = await fetchJsonFromHttps(datastoreUrl);
    if (!response || response.success !== true || !response.result) {
      throw new Error(`Unexpected datastore response for resource ${resource.id}`);
    }
    return response.result;
  }

  throw new Error(
    `Selected resource for package ${packageId} is not JSON. Set CKAN_FETCH_RESOURCE=false to sync package metadata only.`
  );
};

const isCkanPackageSource = (value) => typeof value === 'string' && value.startsWith(CKAN_SOURCE_PREFIX);

const fetchJson = async (source) => {
  if (!source) {
    throw new Error('JSON source is required');
  }

  if (isCkanPackageSource(source)) {
    const packageId = source.slice(CKAN_SOURCE_PREFIX.length).trim();
    if (!packageId) {
      throw new Error('Missing package ID in CKAN source');
    }
    return fetchFromCkanPackage(packageId, process.env.CKAN_BASE_URL || DEFAULT_CKAN_BASE_URL);
  }

  return isHttpSource(source) ? fetchJsonFromHttp(source) : fetchJsonFromFile(source);
};

module.exports = {
  fetchJson,
  getPackageMetadata
};
