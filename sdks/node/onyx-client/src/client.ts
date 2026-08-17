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

  // --- Price Benchmarking & Reports ---

  async benchmark(
    productName: string,
    quantity: number = 1,
    department?: string,
    options: Record<string, any> = {}
  ): Promise<any> {
    try {
      const payload: any = {
        product_name: productName,
        quantity,
        ...options,
      };
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
