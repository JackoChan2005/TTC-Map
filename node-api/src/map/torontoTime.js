const TORONTO_TIMEZONE = 'America/Toronto';
const DAY_MS = 24 * 3600 * 1000;

const WEEKDAY_COLUMNS = new Set([
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
]);

const getTorontoParts = (date) => {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: TORONTO_TIMEZONE,
    weekday: 'long',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });

  const valueByType = {};
  for (const part of formatter.formatToParts(date)) {
    valueByType[part.type] = part.value;
  }

  return {
    weekday: String(valueByType.weekday || '').toLowerCase(),
    sec: (Number.parseInt(valueByType.hour || '0', 10) % 24) * 3600
      + Number.parseInt(valueByType.minute || '0', 10) * 60
      + Number.parseInt(valueByType.second || '0', 10)
  };
};

// GTFS encodes after-midnight service as >24:00:00 on the previous service
// day, so a query must check two windows: today at sec, and yesterday at
// sec + 86400.
const getServiceWindows = (date) => {
  const today = getTorontoParts(date);
  const yesterday = getTorontoParts(new Date(date.getTime() - DAY_MS));

  return [
    { day: today.weekday, sec: today.sec },
    { day: yesterday.weekday, sec: today.sec + 24 * 3600 }
  ].filter((w) => WEEKDAY_COLUMNS.has(w.day));
};

module.exports = {
  TORONTO_TIMEZONE,
  WEEKDAY_COLUMNS,
  getTorontoParts,
  getServiceWindows
};
