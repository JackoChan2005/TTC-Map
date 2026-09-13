const node = (tag, text) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  return element;
};

function endpoint(path, operation) {
  const article = node('article');
  article.append(node('h2', 'GET ' + path), node('p', operation.summary || ''));
  if (operation.description) article.append(node('p', operation.description));
  const form = node('form');
  const parameters = operation.parameters || [];
  for (const parameter of parameters) {
    const label = node('label', parameter.name + (parameter.required ? ' (required)' : ' (optional)'));
    const input = node('input');
    input.name = parameter.name;
    input.required = parameter.required === true;
    input.placeholder = parameter.in === 'path' ? 'e.g. schematic' : '';
    input.value = parameter.schema?.default ?? '';
    label.append(input); form.append(label);
  }
  const submit = node('button', 'Send GET request');
  const status = node('p'); status.setAttribute('role', 'status');
  const output = node('pre'); output.hidden = true;
  form.append(submit);
  form.addEventListener('submit', async event => {
    event.preventDefault(); submit.disabled = true;
    status.textContent = 'Loading…'; output.hidden = true;
    let target = path;
    const query = new URLSearchParams();
    const values = new FormData(form);
    for (const parameter of parameters) {
      const value = String(values.get(parameter.name) || '').trim();
      if (parameter.in === 'path') target = target.replace('{' + parameter.name + '}', encodeURIComponent(value));
      else if (value) query.set(parameter.name, value);
    }
    try {
      const response = await fetch(target + (query.size ? '?' + query : ''), {
        cache: 'no-store', signal: AbortSignal.timeout(15000)
      });
      status.textContent = 'HTTP ' + response.status;
      if (response.headers.get('content-type')?.includes('application/octet-stream')) {
        const bytes = new Uint8Array(await response.arrayBuffer());
        output.textContent = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(' ');
      } else {
        const text = await response.text();
        try { output.textContent = JSON.stringify(JSON.parse(text), null, 2); }
        catch { output.textContent = text; }
      }
      output.hidden = false;
    } catch (error) { status.textContent = 'Request unavailable: ' + error.message; }
    finally { submit.disabled = false; }
  });
  const details = node('details');
  details.append(node('summary', 'OpenAPI operation'), node('pre', JSON.stringify(operation, null, 2)));
  article.append(form, status, output, details);
  return article;
}

const main = document.querySelector('#endpoints');
try {
  const response = await fetch('/openapi.json', { signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const schema = await response.json();
  const entries = Object.entries(schema.paths || {}).filter(([path, item]) => path.startsWith('/api/v1/') && item.get);
  main.replaceChildren(...entries.map(([path, item]) => endpoint(path, item.get)));
  if (!entries.length) main.append(node('p', 'No API endpoints are available.'));
} catch (error) {
  main.replaceChildren(node('p', 'API schema unavailable: ' + error.message + '. Reload to retry.'));
}
