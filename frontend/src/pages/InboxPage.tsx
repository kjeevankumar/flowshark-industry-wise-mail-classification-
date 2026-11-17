import React, { useEffect, useState } from 'react';
import {
  Search,
  RefreshCw,
  Sparkles,
  Paperclip,
  CheckSquare,
  Square,
  ChevronLeft,
  ChevronRight,
  Filter,
  Trash2,
} from 'lucide-react';
import { Email, PaginatedEmails } from '../types';
import { Badge } from '../components/Badge';
import { api } from '../services/api';
import { formatReceivedDateTime } from '../utils/dateUtils';

interface InboxPageProps {
  categoryFilter?: string;
  refreshTrigger?: number;
  onSelectEmail: (email: Email) => void;
  onRefreshSummary: () => void;
}

export const InboxPage: React.FC<InboxPageProps> = ({
  categoryFilter,
  refreshTrigger,
  onSelectEmail,
  onRefreshSummary,
}) => {
  const [data, setData] = useState<PaginatedEmails>({ items: [], total: 0, page: 1, size: 20, pages: 1 });
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [industries, setIndustries] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchClassifying, setBatchClassifying] = useState(false);
  const [cleaningNonBiz, setCleaningNonBiz] = useState(false);
  const [cleanupNotice, setCleanupNotice] = useState<string | null>(null);

  const handleDeleteSingle = async (emailId: number, subject: string) => {
    try {
      await api.deleteEmail(emailId);
      setCleanupNotice(`Removed email "${subject}".`);
      loadEmails(page, categoryFilter, searchTerm, false, industryFilter);
      onRefreshSummary();
      setTimeout(() => setCleanupNotice(null), 4000);
    } catch (err: any) {
      alert('Delete failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCleanupNonBusiness = async () => {
    try {
      setCleaningNonBiz(true);
      const res = await api.cleanupNonBusiness();
      setCleanupNotice(res.message);
      loadEmails(1, categoryFilter, searchTerm, false, industryFilter);
      onRefreshSummary();
      setTimeout(() => setCleanupNotice(null), 5000);
    } catch (err: any) {
      alert('Cleanup failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setCleaningNonBiz(false);
    }
  };

  useEffect(() => {
    api.getIndustries().then((res) => {
      if (res && res.industries) {
        setIndustries(Object.keys(res.industries));
      }
    }).catch((err) => console.error('Failed to load industries:', err));
  }, []);

  useEffect(() => {
    setPage(1);
    setSelectedIds([]);
    loadEmails(1, categoryFilter, searchTerm, false, industryFilter);
  }, [categoryFilter]);

  // Automatic refresh when background sync retrieves new emails
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      loadEmails(page, categoryFilter, searchTerm, true, industryFilter);
    }
  }, [refreshTrigger]);

  const loadEmails = async (
    pageNumber: number,
    category?: string,
    search?: string,
    silent: boolean = false,
    industry?: string
  ) => {
    try {
      if (!silent) setLoading(true);
      const activeIndustry = industry !== undefined ? industry : industryFilter;
      const res = await api.getEmails({
        page: pageNumber,
        size: 20,
        category: category,
        search: search && search.trim() ? search.trim() : undefined,
        industry: activeIndustry && activeIndustry.trim() ? activeIndustry.trim() : undefined,
      });
      setData(res);
    } catch (err) {
      console.error('Failed to load emails:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadEmails(1, categoryFilter, searchTerm, false, industryFilter);
  };

  const handleIndustryChange = (val: string) => {
    setIndustryFilter(val);
    setPage(1);
    loadEmails(1, categoryFilter, searchTerm, false, val);
  };

  const handleToggleSelectAll = () => {
    if (selectedIds.length === data.items.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(data.items.map((em) => em.id));
    }
  };

  const handleToggleSelectOne = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleClassifySelected = async () => {
    if (selectedIds.length === 0) return;
    try {
      setBatchClassifying(true);
      await api.classifyBatch({ email_ids: selectedIds, unclassified_only: false });
      setSelectedIds([]);
      loadEmails(page, categoryFilter, searchTerm);
      onRefreshSummary();
    } catch (err: any) {
      alert('Batch classification failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setBatchClassifying(false);
    }
  };

  const formatCategoryTitle = (cat?: string) => {
    if (!cat) return 'All Synced Emails';
    return cat.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            {formatCategoryTitle(categoryFilter)}
          </h2>
          <p className="text-xs text-slate-500">
            {data.total} email(s) currently matching this view in the local database
          </p>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex items-center space-x-3">
          <div className="relative">
            <select
              value={industryFilter}
              onChange={(e) => handleIndustryChange(e.target.value)}
              className="px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
            >
              <option value="">All Industries</option>
              {industries.map((ind) => (
                <option key={ind} value={ind}>
                  {ind}
                </option>
              ))}
            </select>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search sender, subject..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-4 py-1.5 text-xs bg-white border border-slate-200 rounded-lg w-56 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold shadow-sm"
            >
              Search
            </button>
          </form>

          <button
            onClick={handleCleanupNonBusiness}
            disabled={cleaningNonBiz}
            className="px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded-lg shadow-sm transition-colors flex items-center space-x-1 disabled:opacity-50"
            title="Purge all non-business alerts and newsletters"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{cleaningNonBiz ? 'Purging...' : 'Clean Non-Business'}</span>
          </button>
        </div>
      </div>

      {/* Action Bar (when emails are selected) */}
      {selectedIds.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs animate-fade-in">
          <span className="font-semibold text-indigo-900">
            {selectedIds.length} email(s) selected
          </span>
          <button
            onClick={handleClassifySelected}
            disabled={batchClassifying}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-sm disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 ${batchClassifying ? 'animate-spin' : ''}`} />
            <span>{batchClassifying ? 'Classifying...' : 'Classify Selected'}</span>
          </button>
        </div>
      )}

      {/* Notification Toast */}
      {cleanupNotice && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2.5 text-xs text-emerald-800 font-semibold flex items-center justify-between animate-in fade-in">
          <span>{cleanupNotice}</span>
          <button onClick={() => setCleanupNotice(null)} className="text-emerald-600 hover:text-emerald-900 font-bold">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
              <tr>
                <th className="px-4 py-3 w-10">
                  <button onClick={handleToggleSelectAll} className="text-slate-400 hover:text-slate-600">
                    {selectedIds.length > 0 && selectedIds.length === data.items.length ? (
                      <CheckSquare className="w-4 h-4 text-indigo-600" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                <th className="px-4 py-3">Sender</th>
                <th className="px-4 py-3">Subject & Preview</th>
                <th className="px-4 py-3">Relevance</th>
                <th className="px-4 py-3">Relationship</th>
                <th className="px-4 py-3">Intent</th>
                <th className="px-4 py-3">Lead Stage</th>
                <th className="px-4 py-3">Industry</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Received</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={11} className="p-8 text-center text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                    <span>Loading emails...</span>
                  </td>
                </tr>
              ) : data.items.length === 0 ? (
                <tr>
                  <td colSpan={11} className="p-12 text-center text-slate-500">
                    <Filter className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="font-semibold text-slate-700">
                      {categoryFilter === 'system_notifications'
                        ? 'Zero non-business alerts in database'
                        : 'No emails found'}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      {categoryFilter === 'system_notifications'
                        ? 'All Google security notifications and system noise have been purged.'
                        : 'Try resetting search filters or synchronizing new emails.'}
                    </p>
                  </td>
                </tr>
              ) : (
                data.items.map((email) => {
                  const isSelected = selectedIds.includes(email.id);
                  const c = email.classification;
                  return (
                    <tr
                      key={email.id}
                      onClick={() => onSelectEmail(email)}
                      className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                        isSelected ? 'bg-indigo-50/30' : ''
                      }`}
                    >
                      <td className="px-4 py-3" onClick={(e) => handleToggleSelectOne(email.id, e)}>
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-indigo-600" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-300 hover:text-slate-500" />
                        )}
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-900 max-w-[180px] truncate">
                        {email.sender}
                      </td>
                      <td className="px-4 py-3 max-w-[300px]">
                        <div className="flex items-center space-x-1.5">
                          {email.has_attachments && <Paperclip className="w-3 h-3 text-slate-400 flex-shrink-0" />}
                          <p className="font-medium text-slate-800 truncate">{email.subject}</p>
                        </div>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{email.snippet}</p>
                      </td>
                      <td className="px-4 py-3">
                        {c?.relevance_category ? (
                          <Badge type="relevance" value={c.relevance_category} />
                        ) : c ? (
                          <Badge type="relevance" value={c.is_business_relevant ? 'business_conversation' : 'system_notification'} />
                        ) : (
                          <span className="text-slate-400">Unclassified</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c ? <Badge type="relationship" value={c.relationship} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-4 py-3">
                        {c ? <Badge type="intent" value={c.intent} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-4 py-3">
                        {c ? <Badge type="stage" value={c.lead_stage} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-4 py-3">
                        {c && (c.target_industry || c.sender_industry) ? (
                          <div className="space-y-0.5">
                            <Badge type="industry" value={c.target_industry || c.sender_industry || 'Unknown'} />
                            {c.sub_industry && (
                              <p className="text-[10px] text-slate-400 truncate max-w-[130px]">{c.sub_industry}</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c ? <Badge type="confidence" value={c.confidence} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap text-xs font-medium">
                        {formatReceivedDateTime(email.received_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteSingle(email.id, email.subject);
                          }}
                          title="Delete email from FlowShark"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span>
            Page {data.page} of {data.pages} ({data.total} total items)
          </span>
          <div className="flex items-center space-x-1.5">
            <button
              onClick={() => {
                if (page > 1) {
                  setPage(page - 1);
                  loadEmails(page - 1, categoryFilter, searchTerm);
                }
              }}
              disabled={page <= 1}
              className="p-1 rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                if (page < data.pages) {
                  setPage(page + 1);
                  loadEmails(page + 1, categoryFilter, searchTerm);
                }
              }}
              disabled={page >= data.pages}
              className="p-1 rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

