import axios, { AxiosInstance } from 'axios';

export class OnyxError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'OnyxError';
  }
}

export interface ClientOptions {
  apiKey: string;
  baseUrl?: string;
}

export class OnyxClient {
  private client: AxiosInstance;

  constructor(options: ClientOptions) {
    const baseUrl = options.baseUrl || 'http://localhost:8000';
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        'x-api-key': options.apiKey,
        'Content-Type': 'application/json',
      },
    });
  }

  async fetch(url: string, options: any = {}): Promise<any> {
    try {
      const response = await this.client.post('/fetch', { url, ...options });
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  // --- Crawl API ---

  async startCrawl(url: string, options: any = {}): Promise<any> {
    try {
      const response = await this.client.post('/api/crawl', { url, ...options });
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  async getCrawl(crawlId: string): Promise<any> {
    try {
      const response = await this.client.get(`/api/crawl/${crawlId}`);
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  async listCrawls(): Promise<any[]> {
    try {
      const response = await this.client.get('/api/crawl');
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  async deleteCrawl(crawlId: string): Promise<any> {
    try {
      const response = await this.client.delete(`/api/crawl/${crawlId}`);
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  // --- Price Benchmarking & Reports ---

  async benchmark(query: string, quantity: number = 1, department?: string): Promise<any> {
    try {
      const payload: any = { query, quantity };
      if (department) {
        payload.department = department;
      }
      const response = await this.client.post('/api/v1/benchmark', payload);
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  async generateReport(searchId: string): Promise<any> {
    try {
      const response = await this.client.post(
        '/api/v1/reports/generate',
        { search_id: searchId },
        { responseType: 'arraybuffer' }
      );
      return response.data;
    } catch (error: any) {
      this.handleError(error);
    }
  }

  private handleError(error: any): never {
    if (error.response) {
      const detail = error.response.data?.detail || error.response.data;
      throw new OnyxError(`HTTP ${error.response.status}: ${JSON.stringify(detail)}`);
    }
    throw new OnyxError(error.message);
  }
}
