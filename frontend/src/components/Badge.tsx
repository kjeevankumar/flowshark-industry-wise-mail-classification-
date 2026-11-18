import React from 'react';
import { Relationship, Intent, LeadStage } from '../types';

interface BadgeProps {
  type: 'relationship' | 'intent' | 'stage' | 'confidence' | 'method' | 'industry' | 'relevance' | 'pipeline' | 'classification';
  value: string | number;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ type, value, className = '' }) => {
  if (type === 'classification' || type === 'pipeline') {
    const rawVal = String(value || '').toLowerCase().trim();
    const canonicalMap: Record<string, string> = {
      new_leads: 'new_leads',
      new_enquiry: 'new_leads',
      new_lead: 'new_leads',
      negotiations: 'negotiations',
      negotiation: 'negotiations',
      follow_ups: 'follow_ups',
      follow_up: 'follow_ups',
      clarifications: 'clarifications',
      business_clarification: 'clarifications',
      clarification: 'clarifications',
      existing_leads: 'existing_leads',
      existing_lead: 'existing_leads',
      purchase_orders: 'purchase_orders',
      purchase_order: 'purchase_orders',
      invoices: 'invoices',
      invoice: 'invoices',
      needs_review: 'needs_review',
      review: 'needs_review',
      other: 'needs_review',
      complaint: 'needs_review',
      system_notification: 'system_notification',
      account_security_notification: 'system_notification',
      non_business: 'system_notification',
    };
    const key = canonicalMap[rawVal] || (rawVal.includes('security') || rawVal.includes('system') ? 'system_notification' : 'needs_review');

    const styles: Record<string, string> = {
      new_leads: 'bg-emerald-50 text-emerald-700 border-emerald-300 font-semibold',
      negotiations: 'bg-amber-50 text-amber-700 border-amber-300 font-semibold',
      follow_ups: 'bg-sky-50 text-sky-700 border-sky-300 font-semibold',
      clarifications: 'bg-cyan-50 text-cyan-700 border-cyan-300 font-semibold',
      existing_leads: 'bg-blue-50 text-blue-700 border-blue-300 font-semibold',
      purchase_orders: 'bg-teal-50 text-teal-700 border-teal-300 font-semibold',
      invoices: 'bg-violet-50 text-violet-700 border-violet-300 font-semibold',
      needs_review: 'bg-rose-50 text-rose-700 border-rose-300 font-semibold',
      system_notification: 'bg-slate-100 text-slate-600 border-slate-300 font-medium',
    };
    const labels: Record<string, string> = {
      new_leads: 'New Lead',
      negotiations: 'Negotiation',
      follow_ups: 'Follow-up',
      clarifications: 'Clarification',
      existing_leads: 'Existing Lead',
      purchase_orders: 'Purchase Order',
      invoices: 'Invoice',
      needs_review: 'Needs Review',
      system_notification: 'System Alert',
    };
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs border ${styles[key] || 'bg-slate-100 text-slate-600 border-slate-200'} ${className}`}>
        {labels[key] || rawVal}
      </span>
    );
  }
  if (type === 'relevance') {
    const val = String(value);
    const styles: Record<string, string> = {
      business_enquiry: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      business_conversation: 'bg-blue-50 text-blue-700 border-blue-200',
      purchase_commercial: 'bg-teal-50 text-teal-700 border-teal-200',
      customer_support: 'bg-cyan-50 text-cyan-700 border-cyan-200',
      internal_communication: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      account_security_notification: 'bg-rose-50 text-rose-700 border-rose-200',
      system_notification: 'bg-amber-50 text-amber-700 border-amber-200',
      automated_notification: 'bg-slate-100 text-slate-600 border-slate-200',
      newsletter_marketing: 'bg-purple-50 text-purple-700 border-purple-200',
      spam_irrelevant: 'bg-zinc-100 text-zinc-600 border-zinc-200',
      unknown_review: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    };
    const labels: Record<string, string> = {
      business_enquiry: 'Business Enquiry',
      business_conversation: 'Business Conversation',
      purchase_commercial: 'Commercial / Order',
      customer_support: 'Customer Support',
      internal_communication: 'Internal Comms',
      account_security_notification: 'Security Alert',
      system_notification: 'System Alert',
      automated_notification: 'Automated Alert',
      newsletter_marketing: 'Newsletter / Marketing',
      spam_irrelevant: 'Spam / Irrelevant',
      unknown_review: 'Under Review',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || 'bg-slate-100 text-slate-600 border-slate-200'} ${className}`}>
        {labels[val] || val.replace(/_/g, ' ')}
      </span>
    );
  }



  if (type === 'relationship') {
    const val = value as Relationship;
    if (val === 'not_applicable') {
      return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-50 text-slate-400 border-slate-200 ${className}`}>
          N/A
        </span>
      );
    }
    const styles: Record<Relationship, string> = {
      new_contact: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      existing_lead: 'bg-blue-50 text-blue-700 border-blue-200',
      existing_customer: 'bg-purple-50 text-purple-700 border-purple-200',
      unknown: 'bg-slate-100 text-slate-600 border-slate-200',
      not_applicable: 'bg-slate-50 text-slate-400 border-slate-200',
    };
    const labels: Record<Relationship, string> = {
      new_contact: 'New Contact',
      existing_lead: 'Existing Lead',
      existing_customer: 'Existing Customer',
      unknown: 'Unknown',
      not_applicable: 'N/A',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.unknown} ${className}`}>
        {labels[val] || val}
      </span>
    );
  }

  if (type === 'intent') {
    const val = value as Intent;
    if (val === 'not_applicable') {
      return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-50 text-slate-400 border-slate-200 ${className}`}>
          N/A
        </span>
      );
    }
    const styles: Record<Intent, string> = {
      new_enquiry: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      negotiation: 'bg-amber-50 text-amber-700 border-amber-200',
      follow_up: 'bg-sky-50 text-sky-700 border-sky-200',
      business_clarification: 'bg-cyan-50 text-cyan-700 border-cyan-200',
      purchase_order: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      invoice: 'bg-violet-50 text-violet-700 border-violet-200',
      complaint: 'bg-rose-50 text-rose-700 border-rose-200',
      other: 'bg-slate-100 text-slate-600 border-slate-200',
      not_applicable: 'bg-slate-50 text-slate-400 border-slate-200',
    };
    const labels: Record<Intent, string> = {
      new_enquiry: 'New Enquiry',
      negotiation: 'Negotiation',
      follow_up: 'Follow-up',
      business_clarification: 'Clarification',
      purchase_order: 'Purchase Order',
      invoice: 'Invoice',
      complaint: 'Complaint',
      other: 'Other / News',
      not_applicable: 'N/A',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.other} ${className}`}>
        {labels[val] || val}
      </span>
    );
  }

  if (type === 'stage') {
    const val = value as LeadStage;
    if (val === 'not_applicable') {
      return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-50 text-slate-400 border-slate-200 ${className}`}>
          N/A
        </span>
      );
    }
    const styles: Record<LeadStage, string> = {
      new: 'bg-blue-50 text-blue-700 border-blue-200',
      qualified: 'bg-teal-50 text-teal-700 border-teal-200',
      proposal_sent: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      negotiation: 'bg-amber-50 text-amber-700 border-amber-200',
      won: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      lost: 'bg-rose-50 text-rose-700 border-rose-200',
      unknown: 'bg-slate-100 text-slate-600 border-slate-200',
      not_applicable: 'bg-slate-50 text-slate-400 border-slate-200',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.unknown} ${className}`}>
        {val.replace('_', ' ').toUpperCase()}
      </span>
    );
  }

  if (type === 'industry') {
    const str = String(value);
    if (str === 'Not Applicable' || str === 'not_applicable') {
      return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-50 text-slate-400 border-slate-200 ${className}`}>
          N/A
        </span>
      );
    }
    const styles: Record<string, string> = {
      'Healthcare': 'bg-emerald-50 text-emerald-700 border-emerald-200',
      'IT & Software': 'bg-indigo-50 text-indigo-700 border-indigo-200',
      'Banking & Finance': 'bg-blue-50 text-blue-700 border-blue-200',
      'Manufacturing': 'bg-amber-50 text-amber-700 border-amber-200',
      'Retail & E-commerce': 'bg-purple-50 text-purple-700 border-purple-200',
      'Education': 'bg-cyan-50 text-cyan-700 border-cyan-200',
      'Hospitality & Tourism': 'bg-rose-50 text-rose-700 border-rose-200',
      'Real Estate & Construction': 'bg-orange-50 text-orange-700 border-orange-200',
      'Logistics & Transportation': 'bg-teal-50 text-teal-700 border-teal-200',
      'Agriculture': 'bg-lime-50 text-lime-700 border-lime-200',
      'Energy & Utilities': 'bg-yellow-50 text-yellow-700 border-yellow-200',
      'Marketing & Advertising': 'bg-pink-50 text-pink-700 border-pink-200',
      'Legal & Professional Services': 'bg-violet-50 text-violet-700 border-violet-200',
      'Insurance': 'bg-sky-50 text-sky-700 border-sky-200',
      'Telecommunications': 'bg-indigo-50 text-indigo-700 border-indigo-200',
      'Unknown': 'bg-slate-100 text-slate-500 border-slate-200',
      'Other': 'bg-slate-100 text-slate-600 border-slate-200',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[str] || 'bg-slate-100 text-slate-700 border-slate-200'} ${className}`}>
        {str}
      </span>
    );
  }

  if (type === 'confidence') {
    const num = Number(value);
    const color = num >= 0.85 ? 'text-emerald-600 bg-emerald-50' : num >= 0.60 ? 'text-amber-600 bg-amber-50' : 'text-rose-600 bg-rose-50';
    return (
      <span className={`inline-flex items-center font-semibold px-2 py-0.5 rounded text-xs ${color} ${className}`}>
        {Math.round(num * 100)}%
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 ${className}`}>
      {String(value)}
    </span>
  );
};
