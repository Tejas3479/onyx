# Onyx Node.js Client

Official Node.js client for the Onyx Web Scraping Engine.

## Installation

```bash
npm install onyx-client
```

## Usage

```typescript
import { OnyxClient } from 'onyx-client';

const client = new OnyxClient({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'http://localhost:8000',
});

async function run() {
  const response = await client.fetch('https://example.com', { render_js: true });
  console.log(response.content);
}

run();
```
