const form = document.getElementById('search-form');
const routeInput = document.getElementById('route');
const atTimeInput = document.getElementById('at-time');
const nowBtn = document.getElementById('now-btn');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const bestMatchEl = document.getElementById('best-match');
const matchesEl = document.getElementById('matches');

const toDateTimeLocalValue = (date) => {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const setNow = () => {
  atTimeInput.value = toDateTimeLocalValue(new Date());
};

const formatDateTime = (value) => {
  if (!value) {
    return 'N/A';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
};

const createRecordCard = (record, index = null) => {
  const card = document.createElement('article');
  card.className = 'card';
  const rankLabel = index === null ? 'Best Match' : `Match #${index + 1}`;

  card.innerHTML = `
    <span class="route-pill">${rankLabel}</span>
    <div><strong>Source Key:</strong> ${record.sourceKey || 'N/A'}</div>
    <div><strong>Record Time:</strong> ${formatDateTime(record.recordTime)}</div>
    <div><strong>Updated At:</strong> ${formatDateTime(record.updatedAt)}</div>
    <div><strong>Delta:</strong> ${record.deltaSeconds ?? 'N/A'} sec</div>
    <pre>${JSON.stringify(record.payload, null, 2)}</pre>
  `;

  return card;
};

const showStatus = (message, isError = false) => {
  statusEl.textContent = message;
  statusEl.style.color = isError ? '#9f1239' : '#556173';
};

const clearResults = () => {
  bestMatchEl.innerHTML = '';
  matchesEl.innerHTML = '';
  resultsEl.classList.add('hidden');
};

nowBtn.addEventListener('click', setNow);
form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const route = routeInput.value.trim();
  if (!route) {
    showStatus('Route number is required.', true);
    return;
  }

  const selectedAt = atTimeInput.value ? new Date(atTimeInput.value) : new Date();
  const atIso = Number.isNaN(selectedAt.getTime()) ? new Date().toISOString() : selectedAt.toISOString();
  const url = `/api/route-search?route=${encodeURIComponent(route)}&at=${encodeURIComponent(atIso)}`;

  showStatus('Searching route records...');
  clearResults();

  try {
    const response = await fetch(url);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || 'Route search failed');
    }

    showStatus(`Found ${result.totalMatches} matching record(s) for route ${result.route}.`);
    bestMatchEl.appendChild(createRecordCard(result.bestMatch));

    result.matches.forEach((record, index) => {
      matchesEl.appendChild(createRecordCard(record, index));
    });

    resultsEl.classList.remove('hidden');
  } catch (error) {
    showStatus(error.message, true);
  }
});

setNow();
