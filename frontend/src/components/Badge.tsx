import React from 'react';
import { Relationship, Intent, LeadStage } from '../types';

interface BadgeProps {
  type: 'relationship' | 'intent' | 'stage' | 'confidence' | 'method' | 'industry';
  value: string | number;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ type, value, className = '' }) => {
  if (type === 'relationship') {
    const val = value as Relationship;
    const styles: Record<Relationship, string> = {
      new_contact: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      existing_lead: 'bg-blue-50 text-blue-700 border-blue-200',
      existing_customer: 'bg-purple-50 text-purple-700 border-purple-200',
      unknown: 'bg-slate-100 text-slate-600 border-slate-200',
    };
    const labels: Record<Relationship, string> = {
      new_contact: 'New Contact',
      existing_lead: 'Existing Lead',
      existing_customer: 'Existing Customer',
      unknown: 'Unknown',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.unknown} ${className}`}>
        {labels[val] || val}
      </span>
    );
  }

  if (type === 'intent') {
    const val = value as Intent;
    const styles: Record<Intent, string> = {
      new_enquiry: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      negotiation: 'bg-amber-50 text-amber-700 border-amber-200',
      follow_up: 'bg-sky-50 text-sky-700 border-sky-200',
      business_clarification: 'bg-cyan-50 text-cyan-700 border-cyan-200',
      purchase_order: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      invoice: 'bg-violet-50 text-violet-700 border-violet-200',
      complaint: 'bg-rose-50 text-rose-700 border-rose-200',
      other: 'bg-slate-100 text-slate-600 border-slate-200',
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
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.other} ${className}`}>
        {labels[val] || val}
      </span>
    );
  }

  if (type === 'stage') {
    const val = value as LeadStage;
    const styles: Record<LeadStage, string> = {
      new: 'bg-blue-50 text-blue-700 border-blue-200',
      qualified: 'bg-teal-50 text-teal-700 border-teal-200',
      proposal_sent: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      negotiation: 'bg-amber-50 text-amber-700 border-amber-200',
      won: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      lost: 'bg-rose-50 text-rose-700 border-rose-200',
      unknown: 'bg-slate-100 text-slate-600 border-slate-200',
    };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${styles[val] || styles.unknown} ${className}`}>
        {val.replace('_', ' ').toUpperCase()}
      </span>
    );
  }

  if (type === 'industry') {
    const str = String(value);
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

