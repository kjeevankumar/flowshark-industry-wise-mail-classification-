import React, { useState } from 'react';
import {
  LayoutDashboard,
  MailCheck,
  Inbox,
  Sparkles,
  DollarSign,
  Clock,
  HelpCircle,
  Users,
  FileCheck,
  Receipt,
  CreditCard,
  FileText,
  AlertTriangle,
  Settings,
  Mail,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { DashboardSummary } from '../types';

// Feature flag: Temporarily hide Invoice & Billing and Payments from active dashboard navigation during testing
const SHOW_INVOICE_AND_PAYMENTS = false;

interface SidebarProps {
  currentTab: string;
  categoryFilter?: string;
  onNavigate: (tab: string, category?: string) => void;
  summary: DashboardSummary | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  categoryFilter,
  onNavigate,
  summary,
}) => {
  const [invoiceMenuOpen, setInvoiceMenuOpen] = useState(true);
  const [paymentMenuOpen, setPaymentMenuOpen] = useState(true);

  const isNavActive = (tab: string, cat?: string) => {
    if (tab === 'inbox' && cat) {
      return currentTab === 'inbox' && categoryFilter === cat;
    }
    if (tab === 'inbox' && !cat) {
      return currentTab === 'inbox' && !categoryFilter;
    }
    return currentTab === tab;
  };

  const navClass = (tab: string, cat?: string, isSubItem: boolean = false) => {
    const active = isNavActive(tab, cat);
    return `w-full flex items-center justify-between ${
      isSubItem ? 'pl-7 pr-3 py-1.5 text-xs' : 'px-3 py-2 text-sm'
    } rounded-lg font-medium transition-colors ${
      active
        ? 'bg-indigo-600 text-white shadow-sm'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`;
  };

  const invoiceBillingTotal =
    (summary?.invoice_requests_count ?? 0) +
    (summary?.invoice_updates_count ?? 0) +
    (summary?.invoice_billing_count ?? summary?.invoices_count ?? 0);

  const paymentsTotal =
    (summary?.payment_remittances_count ?? 0) +
    (summary?.payment_followups_count ?? 0) +
    (summary?.payment_disputes_count ?? 0) +
    (summary?.payments_count ?? 0);

  return (
    <aside className="w-64 bg-white border-r border-slate-200 h-screen flex flex-col flex-shrink-0 select-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="h-9 w-9 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-xl flex items-center justify-center text-white shadow-md shadow-indigo-100">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-slate-900 leading-none tracking-tight text-base">FlowShark</h1>
            <span className="text-[10px] text-indigo-600 font-semibold tracking-wider uppercase">AI Email Intelligence</span>
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-5">
        {/* Core Views */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Overview
          </div>
          <button onClick={() => onNavigate('dashboard')} className={navClass('dashboard')}>
            <div className="flex items-center space-x-2.5">
              <LayoutDashboard className="w-4 h-4" />
              <span>Dashboard</span>
            </div>
          </button>
          <button onClick={() => onNavigate('connection')} className={navClass('connection')}>
            <div className="flex items-center space-x-2.5">
              <MailCheck className="w-4 h-4" />
              <span>Email Connection</span>
            </div>
          </button>
          <button onClick={() => onNavigate('inbox')} className={navClass('inbox')}>
            <div className="flex items-center space-x-2.5">
              <Inbox className="w-4 h-4" />
              <span>All Ingested Emails</span>
            </div>
            {summary && summary.total_synced > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${isNavActive('inbox') ? 'bg-indigo-700 text-white' : 'bg-slate-100 text-slate-600'}`}>
                {summary.total_synced}
              </span>
            )}
          </button>
          <button onClick={() => onNavigate('inbox', 'system_notifications')} className={navClass('inbox', 'system_notifications')}>
            <div className="flex items-center space-x-2.5">
              <Mail className="w-4 h-4 text-slate-400" />
              <span>System & Alerts</span>
            </div>
            {summary && (summary.non_business_count ?? 0) > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${isNavActive('inbox', 'system_notifications') ? 'bg-indigo-700 text-white' : 'bg-slate-100 text-slate-600'}`}>
                {summary.non_business_count}
              </span>
            )}
          </button>
        </div>

        {/* Lead Pipelines */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Lead Pipelines
          </div>

          <button onClick={() => onNavigate('inbox', 'new_leads')} className={navClass('inbox', 'new_leads')}>
            <div className="flex items-center space-x-2.5">
              <Sparkles className="w-4 h-4 text-emerald-500" />
              <span>New Leads</span>
            </div>
            {summary && summary.new_leads_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800">
                {summary.new_leads_count}
              </span>
            )}
          </button>

          <button onClick={() => onNavigate('inbox', 'negotiations')} className={navClass('inbox', 'negotiations')}>
            <div className="flex items-center space-x-2.5">
              <DollarSign className="w-4 h-4 text-amber-500" />
              <span>Negotiations</span>
            </div>
            {summary && summary.negotiations_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-800">
                {summary.negotiations_count}
              </span>
            )}
          </button>

          <button onClick={() => onNavigate('inbox', 'follow_ups')} className={navClass('inbox', 'follow_ups')}>
            <div className="flex items-center space-x-2.5">
              <Clock className="w-4 h-4 text-sky-500" />
              <span>Follow-ups</span>
            </div>
            {summary && summary.follow_ups_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-sky-100 text-sky-800">
                {summary.follow_ups_count}
              </span>
            )}
          </button>

          <button onClick={() => onNavigate('inbox', 'business_clarifications')} className={navClass('inbox', 'business_clarifications')}>
            <div className="flex items-center space-x-2.5">
              <HelpCircle className="w-4 h-4 text-cyan-500" />
              <span>Clarifications</span>
            </div>
            {summary && summary.clarifications_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-cyan-100 text-cyan-800">
                {summary.clarifications_count}
              </span>
            )}
          </button>

          <button onClick={() => onNavigate('inbox', 'existing_leads')} className={navClass('inbox', 'existing_leads')}>
            <div className="flex items-center space-x-2.5">
              <Users className="w-4 h-4 text-blue-500" />
              <span>Existing Leads</span>
            </div>
            {summary && summary.existing_leads_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-blue-100 text-blue-800">
                {summary.existing_leads_count}
              </span>
            )}
          </button>
        </div>

        {/* Commercial Pipelines */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Commercial Pipelines
          </div>

          {/* 1. Purchase Orders */}
          <button onClick={() => onNavigate('inbox', 'purchase_orders')} className={navClass('inbox', 'purchase_orders')}>
            <div className="flex items-center space-x-2.5">
              <FileCheck className="w-4 h-4 text-teal-600" />
              <span>Purchase Orders</span>
            </div>
            {summary && summary.purchase_orders_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-teal-100 text-teal-800">
                {summary.purchase_orders_count}
              </span>
            )}
          </button>

          {/* 2. Invoice & Billing Group (Temporarily disabled for core testing) */}
          {SHOW_INVOICE_AND_PAYMENTS && (
            <div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => onNavigate('inbox', 'invoice_billing')}
                  className={`flex-1 flex items-center justify-between px-3 py-2 text-sm rounded-lg font-medium transition-colors ${
                    isNavActive('inbox', 'invoice_billing')
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Receipt className="w-4 h-4 text-violet-500" />
                    <span>Invoice & Billing</span>
                  </div>
                  {invoiceBillingTotal > 0 && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                      isNavActive('inbox', 'invoice_billing') ? 'bg-indigo-700 text-white' : 'bg-violet-100 text-violet-800'
                    }`}>
                      {invoiceBillingTotal}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setInvoiceMenuOpen(!invoiceMenuOpen)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 ml-1"
                  title="Toggle subcategories"
                >
                  {invoiceMenuOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
              </div>

              {invoiceMenuOpen && (
                <div className="mt-0.5 space-y-0.5">
                  <button onClick={() => onNavigate('inbox', 'invoice_request')} className={navClass('inbox', 'invoice_request', true)}>
                    <div className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400"></span>
                      <span>Invoice Request</span>
                    </div>
                    {summary && (summary.invoice_requests_count ?? 0) > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-medium bg-slate-100 text-slate-600">
                        {summary.invoice_requests_count}
                      </span>
                    )}
                  </button>
                  <button onClick={() => onNavigate('inbox', 'invoice_update')} className={navClass('inbox', 'invoice_update', true)}>
                    <div className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                      <span>Invoice Update</span>
                    </div>
                    {summary && (summary.invoice_updates_count ?? 0) > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-medium bg-slate-100 text-slate-600">
                        {summary.invoice_updates_count}
                      </span>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 3. Payments Group (Temporarily disabled for core testing) */}
          {SHOW_INVOICE_AND_PAYMENTS && (
            <div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => onNavigate('inbox', 'payments')}
                  className={`flex-1 flex items-center justify-between px-3 py-2 text-sm rounded-lg font-medium transition-colors ${
                    isNavActive('inbox', 'payments')
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <CreditCard className="w-4 h-4 text-emerald-600" />
                    <span>Payments</span>
                  </div>
                  {paymentsTotal > 0 && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                      isNavActive('inbox', 'payments') ? 'bg-indigo-700 text-white' : 'bg-emerald-100 text-emerald-800'
                    }`}>
                      {paymentsTotal}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setPaymentMenuOpen(!paymentMenuOpen)}
                  className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 ml-1"
                  title="Toggle subcategories"
                >
                  {paymentMenuOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
              </div>

              {paymentMenuOpen && (
                <div className="mt-0.5 space-y-0.5">
                  <button onClick={() => onNavigate('inbox', 'payment_remittance')} className={navClass('inbox', 'payment_remittance', true)}>
                    <div className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      <span>Remittance Advice</span>
                    </div>
                    {summary && (summary.payment_remittances_count ?? 0) > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-medium bg-slate-100 text-slate-600">
                        {summary.payment_remittances_count}
                      </span>
                    )}
                  </button>
                  <button onClick={() => onNavigate('inbox', 'payment_follow_up')} className={navClass('inbox', 'payment_follow_up', true)}>
                    <div className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-sky-500"></span>
                      <span>Payment Follow-up</span>
                    </div>
                    {summary && (summary.payment_followups_count ?? 0) > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-medium bg-slate-100 text-slate-600">
                        {summary.payment_followups_count}
                      </span>
                    )}
                  </button>
                  <button onClick={() => onNavigate('inbox', 'payment_dispute')} className={navClass('inbox', 'payment_dispute', true)}>
                    <div className="flex items-center space-x-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                      <span>Payment Dispute</span>
                    </div>
                    {summary && (summary.payment_disputes_count ?? 0) > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-medium bg-rose-100 text-rose-800">
                        {summary.payment_disputes_count}
                      </span>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}

          <button onClick={() => onNavigate('inbox', 'needs_review')} className={navClass('inbox', 'needs_review')}>
            <div className="flex items-center space-x-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-500" />
              <span>Needs Review</span>
            </div>
            {summary && summary.needs_review_count > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-rose-100 text-rose-800">
                {summary.needs_review_count}
              </span>
            )}
          </button>
        </div>

        {/* System Settings */}
        <div className="space-y-1">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Configuration
          </div>
          <button onClick={() => onNavigate('settings')} className={navClass('settings')}>
            <div className="flex items-center space-x-2.5">
              <Settings className="w-4 h-4" />
              <span>Settings & AI Model</span>
            </div>
          </button>
        </div>
      </div>

      {/* Account Footer */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/50">
        <div className="flex items-center space-x-3 px-2 py-1.5">
          <div className="h-8 w-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
            G
          </div>
          <div className="truncate flex-1">
            <p className="text-xs font-semibold text-slate-800 truncate">Gmail Connected</p>
            <p className="text-[11px] text-slate-500 truncate">IMAP + STARTTLS Active</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

