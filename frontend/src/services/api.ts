import axios from 'axios';
import {
  ConfigStatus,
  ConnectionDetailsResponse,
  DashboardSummary,
  Email,
  PaginatedEmails,
  SwitchMailboxRequest,
  SyncStatus,
  Classification,
  ClassificationHistoryItem,
  EmailContextResponse,
  UpdateConnectionRequest,
  IndustryTaxonomyResponse,
  IndustryAnalyticsResponse,
  IndustryCorrectionRequest,
} from '../types';

// Supports local development (relative '/') as well as cloud deployment (e.g. Vercel -> Render)
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Dashboard & Metrics
  getDashboardSummary: async (): Promise<DashboardSummary> => {
    const res = await apiClient.get<DashboardSummary>('/api/dashboard/summary');
    return res.data;
  },

  getMetrics: async (): Promise<any> => {
    const res = await apiClient.get('/api/classification/metrics');
    return res.data;
  },

  // Connection & Settings
  getConnectionDetails: async (): Promise<ConnectionDetailsResponse> => {
    const res = await apiClient.get<ConnectionDetailsResponse>('/api/email/connection');
    return res.data;
  },

  updateConnection: async (data: UpdateConnectionRequest): Promise<ConnectionDetailsResponse> => {
    const res = await apiClient.put<ConnectionDetailsResponse>('/api/email/connection', data);
    return res.data;
  },

  switchMailbox: async (data: SwitchMailboxRequest): Promise<ConnectionDetailsResponse> => {
    const res = await apiClient.post<ConnectionDetailsResponse>('/api/email/connection/switch', data);
    return res.data;
  },

  getConfigStatus: async (): Promise<ConfigStatus> => {
    const res = await apiClient.get<ConfigStatus>('/api/email/config-status');
    return res.data;
  },

  testIMAP: async (): Promise<any> => {
    const res = await apiClient.get('/api/email/test-imap');
    return res.data;
  },

  testSMTP: async (): Promise<any> => {
    const res = await apiClient.get('/api/email/test-smtp');
    return res.data;
  },

  // Synchronization
  getSyncStatus: async (): Promise<SyncStatus> => {
    const res = await apiClient.get<SyncStatus>('/api/email/sync-status');
    return res.data;
  },

  triggerSync: async (batchSize: number = 50): Promise<any> => {
    const res = await apiClient.post('/api/emails/sync', { batch_size: batchSize });
    return res.data;
  },

  // Emails & Inbox
  getEmails: async (params: {
    page?: number;
    size?: number;
    search?: string;
    category?: string;
    is_business_relevant?: boolean;
    pipeline_category?: string;
    relevance_category?: string;
    intent?: string;
    relationship?: string;
    lead_stage?: string;
    industry?: string;
    sender_industry?: string;
    target_industry?: string;
  }): Promise<PaginatedEmails> => {
    const res = await apiClient.get<PaginatedEmails>('/api/emails', { params });
    return res.data;
  },

  getEmailDetail: async (id: number): Promise<Email> => {
    const res = await apiClient.get<Email>(`/api/emails/${id}`);
    return res.data;
  },

  getThreadEmails: async (threadId: string): Promise<Email[]> => {
    const res = await apiClient.get<Email[]>(`/api/emails/threads/${threadId}`);
    return res.data;
  },

  // AI Classification
  classifyEmail: async (emailId: number): Promise<Classification> => {
    const res = await apiClient.post<Classification>(`/api/classification/classify/${emailId}`);
    return res.data;
  },

  classifyBatch: async (params: {
    email_ids?: number[];
    unclassified_only?: boolean;
    limit?: number;
  }): Promise<any> => {
    const res = await apiClient.post('/api/classification/classify-batch', params);
    return res.data;
  },

  correctClassification: async (
    classificationId: number,
    correction: {
      relevance_category?: string;
      is_business_relevant?: boolean;
      pipeline_category?: string;
      relationship?: string;
      intent?: string;
      lead_stage?: string;
      sender_industry?: string;
      target_industry?: string;
      sub_industry?: string;
      notes?: string;
    }
  ): Promise<Classification> => {
    const res = await apiClient.patch<Classification>(
      `/api/classification/${classificationId}/correct`,
      correction
    );
    return res.data;
  },

  // Industry Classification APIs (Section 9)
  getIndustries: async (): Promise<IndustryTaxonomyResponse> => {
    const res = await apiClient.get<IndustryTaxonomyResponse>('/api/industries');
    return res.data;
  },

  getIndustryAnalytics: async (): Promise<IndustryAnalyticsResponse> => {
    const res = await apiClient.get<IndustryAnalyticsResponse>('/api/analytics/industries');
    return res.data;
  },

  updateIndustryClassification: async (
    classificationId: number,
    data: IndustryCorrectionRequest
  ): Promise<Classification> => {
    const res = await apiClient.put<Classification>(
      `/api/classifications/${classificationId}/industry`,
      data
    );
    return res.data;
  },

  getEmailContext: async (emailId: number): Promise<EmailContextResponse> => {
    const res = await apiClient.get<EmailContextResponse>(`/api/classification/${emailId}/context`);
    return res.data;
  },

  getEmailHistory: async (emailId: number): Promise<ClassificationHistoryItem[]> => {
    const res = await apiClient.get<ClassificationHistoryItem[]>(`/api/classification/${emailId}/history`);
    return res.data;
  },

  backfillClassifications: async (): Promise<any> => {
    const res = await apiClient.post('/api/classification/backfill');
    return res.data;
  },
};

