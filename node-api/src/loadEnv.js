const path = require('path');
const dotenv = require('dotenv');

// .env.local (gitignored, machine-specific overrides) is loaded first:
// dotenv never overwrites variables that are already set, so values here
// take precedence over the committed defaults in env.config.
dotenv.config({ path: path.resolve(__dirname, '..', '.env.local') });
dotenv.config({ path: path.resolve(__dirname, '..', 'env.config') });
