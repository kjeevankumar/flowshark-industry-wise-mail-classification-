import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  DollarSign,
  Clock,
  Users,
  AlertTriangle,
  Inbox,
  CheckCircle2,
  ArrowUpRight,
  TrendingUp,
  FileCheck,
  Receipt,
  HelpCircle,
  Building2,
  Briefcase,
  PieChart,
} from 'lucide-react';
import { DashboardSummary, Email, IndustryAnalyticsResponse } from '../types';
import { Badge } from '../components/Badge';
import { api } from '../services/api';

interface DashboardPageProps {
  summary: DashboardSummary | null;
  onNavigate: (tab: string, category?: string) => void;
  onSelectEmail: (email: Email) => void;
  onRefresh: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  summary,
  onNavigate,
  onSelectEmail,
  onRefresh,
}) => {
  const [batchClassifying, setBatchClassifying] = useState(false);
  const [batchMsg, setBatchMsg] = useState<string | null>(null);
  const [industryAnalytics, setIndustryAnalytics] = useState<IndustryAnalyticsResponse | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  useEffect(() => {
    loadIndustryAnalytics();
  }, [summary?.total_classified]);

  const loadIndustryAnalytics = async () => {
    try {
      setLoadingAnalytics(true);
      const data = await api.getIndustryAnalytics();
      setIndustryAnalytics(data);
    } catch (err) {
      console.error('Failed to load industry analytics:', err);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const handleBatchClassify = async () => {
    try {
      setBatchClassifying(true);
      setBatchMsg('Classifying unclassified emails...');
      const res = await api.classifyBatch({ unclassified_only: true, limit: 20 });
      setBatchMsg(`Classified ${res.successful_count} emails.`);
      onRefresh();
      loadIndustryAnalytics();
      setTimeout(() => setBatchMsg(null), 4000);
    } catch (err: any) {
      setBatchMsg('Batch error: ' + (err.response?.data?.detail || err.message));
      setTimeout(() => setBatchMsg(null), 5000);
    } finally {
      setBatchClassifying(false);
    }
  };

  const cards = [
    {
      title: 'New Leads',
      count: summary?.new_leads_count ?? 0,
      icon: Sparkles,
      color: 'emerald',
      bg: 'bg-emerald-50 text-emerald-600',
      tab: 'inbox',
      category: 'new_leads',
      desc: 'First-time inbound enquiries',
    },
    {
      title: 'Negotiations',
      count: summary?.negotiations_count ?? 0,
      icon: DollarSign,
      color: 'amber',
      bg: 'bg-amber-50 text-amber-600',
      tab: 'inbox',
      category: 'negotiations',
      desc: 'Pricing & discount discussions',
    },
    {
      title: 'Follow-ups',
      count: summary?.follow_ups_count ?? 0,
      icon: Clock,
      color: 'sky',
      bg: 'bg-sky-50 text-sky-600',
      tab: 'inbox',
      category: 'follow_ups',
      desc: 'Awaiting proposals or responses',
    },
    {
      title: 'Existing Leads',
      count: summary?.existing_leads_count ?? 0,
      icon: Users,
      color: 'blue',
      bg: 'bg-blue-50 text-blue-600',
      tab: 'inbox',
      category: 'existing_leads',
      desc: 'In-progress opportunities',
    },
    {
      title: 'Clarifications',
      count: summary?.clarifications_count ?? 0,
      icon: HelpCircle,
      color: 'cyan',
      bg: 'bg-cyan-50 text-cyan-600',
      tab: 'inbox',
      category: 'business_clarifications',
      desc: 'Technical & scope questions',
    },
    {
      title: 'Needs Review',
      count: summary?.needs_review_count ?? 0,
      icon: AlertTriangle,
      color: 'rose',
      bg: 'bg-rose-50 text-rose-600',
      tab: 'inbox',
      category: 'needs_review',
      desc: 'Low confidence / conflicting',
    },
  ];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Banner / Pipeline Header */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 opacity-10 flex items-center pr-10 pointer-events-none">
          <TrendingUp className="w-64 h-64" />
        </div>
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-200 text-xs font-semibold border border-indigo-400/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI-Driven Lead Classification Active</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Enterprise Inbox Intelligence</h2>
          <p className="text-slate-300 text-xs leading-relaxed">
            FlowShark continuously monitors your Gmail inbox via non-destructive IMAP, runs NLP noise filtering, detects commercial signals, and structures inbound communications into sales pipeline stages.
          </p>

          <div className="flex items-center space-x-3 pt-2">
            <button
              onClick={handleBatchClassify}
              disabled={batchClassifying}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-md transition-all flex items-center space-x-2 disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 ${batchClassifying ? 'animate-spin' : ''}`} />
              <span>{batchClassifying ? 'Processing...' : 'Classify Next 20 Emails'}</span>
            </button>
            <button
              onClick={() => onNavigate('inbox')}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-xs font-bold rounded-lg transition-colors border border-white/10"
            >
              View Ingested Emails ({summary?.total_synced ?? 0})
            </button>
            {batchMsg && <span className="text-xs text-indigo-300 font-medium animate-pulse">{batchMsg}</span>}
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-3 gap-5">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              onClick={() => onNavigate(card.tab, card.category)}
              className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group flex flex-col justify-between"
            >
              <div className="flex items-center justify-between">
                <div className={`p-2 rounded-lg ${card.bg}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
              </div>
              <div className="mt-4">
                <span className="text-2xl font-extrabold text-slate-900 tracking-tight">{card.count}</span>
                <h3 className="text-xs font-bold text-slate-700 mt-0.5">{card.title}</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">{card.desc}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Overview Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Total Synced In DB</span>
          <p className="text-xl font-bold text-slate-900 mt-1">{summary?.total_synced ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">AI Classified</span>
          <p className="text-xl font-bold text-indigo-600 mt-1">{summary?.total_classified ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Human Corrections</span>
          <p className="text-xl font-bold text-slate-900 mt-1">{summary?.human_corrected_count ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Active Model Engine</span>
          <p className="text-sm font-bold text-slate-800 mt-1 truncate capitalize">
            {summary?.active_llm_provider || 'Hybrid AI'}
          </p>
        </div>
      </div>

      {/* Industry Intelligence & Analytics Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900">Industry Intelligence & Sector Analytics</h3>
              <p className="text-xs text-slate-500">
                Automated multi-dimensional classification of sender vs target industries across B2B communications
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate('inbox')}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
          >
            <span>Filter Inbox by Industry</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {loadingAnalytics ? (
          <div className="p-8 text-center text-slate-400">
            <span className="text-xs">Loading industry metrics...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Target Industries Breakdown */}
            <div className="bg-slate-50/70 rounded-xl p-4 border border-slate-100 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 flex items-center space-x-1.5">
                  <PieChart className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Target Industry Distribution</span>
                </span>
                <span className="text-[11px] text-slate-400">
                  {industryAnalytics?.total_classified ?? 0} classified
                </span>
              </div>

              {industryAnalytics?.target_industry_distribution && industryAnalytics.target_industry_distribution.length > 0 ? (
                <div className="space-y-2.5">
                  {industryAnalytics.target_industry_distribution.slice(0, 5).map((item, idx) => {
                    const name = item.target_industry || item.industry || 'Unknown';
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-700 truncate max-w-[200px]">
                            {name}
                          </span>
                          <div className="flex items-center space-x-2">
                            <span className="font-semibold text-slate-900">{item.count}</span>
                            <span className="text-[11px] text-slate-400 w-10 text-right">{item.percentage}%</span>
                          </div>
                        </div>
                        <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(100, Math.max(5, item.percentage))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-4 text-center">No industry data available</p>
              )}
            </div>

            {/* Inbound Commercial Intent by Industry */}
            <div className="bg-slate-50/70 rounded-xl p-4 border border-slate-100 space-y-3">
              <span className="text-xs font-bold text-slate-800 flex items-center space-x-1.5">
                <Briefcase className="w-3.5 h-3.5 text-emerald-500" />
                <span>Sector Demand (New Enquiries & Follow-ups)</span>
              </span>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="bg-white p-3 rounded-lg border border-slate-200/60 shadow-xs">
                  <span className="text-[10px] uppercase font-bold text-emerald-700 block mb-1.5">
                    Top New Enquiries
                  </span>
                  {industryAnalytics?.new_enquiries_by_industry &&
                  Object.keys(industryAnalytics.new_enquiries_by_industry).length > 0 ? (
                    <div className="space-y-1">
                      {Object.entries(industryAnalytics.new_enquiries_by_industry)
                        .slice(0, 3)
                        .map(([ind, cnt]) => (
                          <div key={ind} className="flex items-center justify-between text-xs">
                            <span className="text-slate-600 truncate max-w-[110px]">{ind}</span>
                            <span className="font-bold text-slate-800 bg-emerald-50 px-1.5 py-0.5 rounded text-[11px]">
                              {cnt}
                            </span>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-400">None recorded</p>
                  )}
                </div>

                <div className="bg-white p-3 rounded-lg border border-slate-200/60 shadow-xs">
                  <span className="text-[10px] uppercase font-bold text-sky-700 block mb-1.5">
                    Top Follow-ups
                  </span>
                  {industryAnalytics?.follow_ups_by_industry &&
                  Object.keys(industryAnalytics.follow_ups_by_industry).length > 0 ? (
                    <div className="space-y-1">
                      {Object.entries(industryAnalytics.follow_ups_by_industry)
                        .slice(0, 3)
                        .map(([ind, cnt]) => (
                          <div key={ind} className="flex items-center justify-between text-xs">
                            <span className="text-slate-600 truncate max-w-[110px]">{ind}</span>
                            <span className="font-bold text-slate-800 bg-sky-50 px-1.5 py-0.5 rounded text-[11px]">
                              {cnt}
                            </span>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-400">None recorded</p>
                  )}
                </div>
              </div>

              {/* Sender Sectors Summary */}
              {industryAnalytics?.total_by_industry && Object.keys(industryAnalytics.total_by_industry).length > 0 && (
                <div className="pt-1 flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] text-slate-400 font-semibold mr-1">Sender Sectors:</span>
                  {Object.entries(industryAnalytics.total_by_industry).slice(0, 4).map(([sInd, cnt]) => (
                    <span key={sInd} className="px-2 py-0.5 bg-slate-200 text-slate-700 text-[10px] font-medium rounded-full">
                      {sInd} ({cnt})
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Recent Activity Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-slate-900">Recent Synced Inbound Communications</h3>
            <p className="text-xs text-slate-500">Live preview of synchronized emails and AI classification statuses</p>
          </div>
          <button
            onClick={() => onNavigate('inbox')}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            View All &rarr;
          </button>
        </div>

        {summary?.recent_activity && summary.recent_activity.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase text-[10px]">
                <tr>
                  <th className="px-5 py-3">Sender</th>
                  <th className="px-5 py-3">Subject</th>
                  <th className="px-5 py-3">Relationship</th>
                  <th className="px-5 py-3">Intent</th>
                  <th className="px-5 py-3">Stage</th>
                  <th className="px-5 py-3">Industry</th>
                  <th className="px-5 py-3">Confidence</th>
                  <th className="px-5 py-3">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {summary.recent_activity.map((email) => {
                  const c = email.classification;
                  return (
                    <tr
                      key={email.id}
                      onClick={() => onSelectEmail(email)}
                      className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3.5 font-semibold text-slate-900 max-w-[180px] truncate">
                        {email.sender}
                      </td>
                      <td className="px-5 py-3.5 max-w-[280px]">
                        <p className="font-medium text-slate-800 truncate">{email.subject}</p>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{email.snippet}</p>
                      </td>
                      <td className="px-5 py-3.5">
                        {c ? <Badge type="relationship" value={c.relationship} /> : <span className="text-slate-400">Unclassified</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        {c ? <Badge type="intent" value={c.intent} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        {c ? <Badge type="stage" value={c.lead_stage} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        {c && (c.target_industry || c.sender_industry) ? (
                          <div className="space-y-0.5">
                            <Badge type="industry" value={c.target_industry || c.sender_industry || 'Unknown'} />
                            {c.sub_industry && (
                              <p className="text-[10px] text-slate-400 truncate max-w-[120px]">{c.sub_industry}</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        {c ? <Badge type="confidence" value={c.confidence} /> : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 whitespace-nowrap">
                        {email.received_at ? new Date(email.received_at).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center space-y-2">
            <Inbox className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-700">No emails synchronized yet</p>
            <p className="text-xs text-slate-500">Go to the Email Connection page to synchronize your Gmail INBOX.</p>
          </div>
        )}
      </div>
    </div>
  );
};

