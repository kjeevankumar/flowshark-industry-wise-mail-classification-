import React, { useEffect, useState } from 'react';
import {
  X,
  Sparkles,
  Paperclip,
  CheckCircle,
  AlertTriangle,
  History,
  Send,
  MessageSquare,
  ArrowRight,
  Edit3,
  User,
  Briefcase,
  GitBranch,
  Clock,
  Building2,
  Trash2,
  TrendingUp,
  Receipt,
} from 'lucide-react';
import { Email, Classification, ClassificationHistoryItem, EmailContextResponse } from '../types';
import { Badge } from './Badge';
import { api } from '../services/api';
import { formatReceivedDateTime, parseServerDate } from '../utils/dateUtils';

interface EmailDetailModalProps {
  email: Email | null;
  onClose: () => void;
  onUpdated: () => void;
}

export const EmailDetailModal: React.FC<EmailDetailModalProps> = ({
  email,
  onClose,
  onUpdated,
}) => {
  const [threadEmails, setThreadEmails] = useState<Email[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [showCorrectionForm, setShowCorrectionForm] = useState(false);

  // Context & Audit History state
  const [emailContext, setEmailContext] = useState<EmailContextResponse | null>(null);
  const [auditHistory, setAuditHistory] = useState<ClassificationHistoryItem[]>([]);
  const [loadingContext, setLoadingContext] = useState(false);
  const [taxonomy, setTaxonomy] = useState<Record<string, string[]>>({});

  // Correction form fields
  const [corrRelevance, setCorrRelevance] = useState<string>('business_conversation');
  const [corrPipeline, setCorrPipeline] = useState<string>('new_leads');
  const [corrIsBiz, setCorrIsBiz] = useState<boolean>(true);
  const [corrRelationship, setCorrRelationship] = useState<string>('');
  const [corrIntent, setCorrIntent] = useState<string>('');
  const [corrStage, setCorrStage] = useState<string>('');
  const [corrSenderIndustry, setCorrSenderIndustry] = useState<string>('Unknown');
  const [corrTargetIndustry, setCorrTargetIndustry] = useState<string>('Unknown');
  const [corrSubIndustry, setCorrSubIndustry] = useState<string>('');
  const [corrNotes, setCorrNotes] = useState<string>('');
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteEmail = async () => {
    if (!email) return;
    if (!window.confirm(`Are you sure you want to remove email "${email.subject}" from FlowShark?`)) {
      return;
    }
    try {
      setDeleting(true);
      await api.deleteEmail(email.id);
      onUpdated();
      onClose();
    } catch (err: any) {
      alert('Delete failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    api.getIndustries().then((res) => setTaxonomy(res.industries)).catch(() => {});
  }, []);

  useEffect(() => {
    if (email) {
      if (email.classification) {
        setCorrRelevance(email.classification.relevance_category || 'business_conversation');
        setCorrPipeline(email.classification.pipeline_category || 'new_leads');
        setCorrIsBiz(email.classification.is_business_relevant ?? true);
        setCorrRelationship(email.classification.relationship);
        setCorrIntent(email.classification.intent);
        setCorrStage(email.classification.lead_stage);
        setCorrSenderIndustry(email.classification.sender_industry || 'Unknown');
        setCorrTargetIndustry(email.classification.target_industry || 'Unknown');
        setCorrSubIndustry(email.classification.sub_industry || '');
      }
      loadDetails(email);
    }
  }, [email]);

  const loadDetails = async (targetEmail: Email) => {
    try {
      setLoadingContext(true);
      // 1. Thread emails
      if (targetEmail.gmail_thread_id) {
        api.getThreadEmails(targetEmail.gmail_thread_id).then(setThreadEmails).catch(() => setThreadEmails([]));
      } else {
        setThreadEmails([]);
      }

      // 2. Conversation context
      api.getEmailContext(targetEmail.id).then(setEmailContext).catch(() => setEmailContext(null));

      // 3. Classification audit history
      api.getEmailHistory(targetEmail.id).then(setAuditHistory).catch(() => setAuditHistory([]));
    } finally {
      setLoadingContext(false);
    }
  };

  if (!email) return null;

  const handleClassifyNow = async () => {
    try {
      setClassifying(true);
      await api.classifyEmail(email.id);
      loadDetails(email);
      onUpdated();
    } catch (err: any) {
      alert('Classification failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setClassifying(false);
    }
  };

  const handleSaveCorrection = async () => {
    if (!email.classification) return;
    try {
      setSavingCorrection(true);
      await api.correctClassification(email.classification.id, {
        relevance_category: corrRelevance,
        pipeline_category: corrIsBiz ? corrPipeline : undefined,
        is_business_relevant: corrIsBiz,
        relationship: corrRelationship,
        intent: corrIntent,
        lead_stage: corrStage,
        sender_industry: corrSenderIndustry,
        target_industry: corrTargetIndustry,
        sub_industry: corrSubIndustry || undefined,
        notes: corrNotes,
      });
      setShowCorrectionForm(false);
      loadDetails(email);
      onUpdated();
    } catch (err: any) {
      alert('Correction failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingCorrection(false);
    }
  };

  const cls = email.classification;
  const leadTitle = email.lead?.title || emailContext?.lead_title;
  const leadStage = email.lead?.status || emailContext?.lead_stage;
  const contextUsed = cls?.context_used || emailContext?.context_used;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end transition-opacity">
      <div className="w-full max-w-3xl bg-white h-full shadow-2xl flex flex-col animate-slide-in overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="truncate pr-4">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              IMAP UID: {email.imap_uid} {email.gmail_thread_id ? `| Thread: ${email.gmail_thread_id}` : ''}
            </span>
            <h3 className="text-base font-bold text-slate-900 truncate mt-0.5">{email.subject}</h3>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleDeleteEmail}
              disabled={deleting}
              title="Remove this email from FlowShark"
              className="p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors flex items-center space-x-1 text-xs font-semibold"
            >
              <Trash2 className="w-4 h-4" />
              <span className="hidden sm:inline">{deleting ? 'Removing...' : 'Delete'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Metadata Grid */}
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-xs space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-slate-500 font-medium">From:</span>
              <div className="flex items-center space-x-2">
                <span className="text-slate-800 font-semibold truncate max-w-md">{email.sender}</span>
                {cls && <Badge type="relationship" value={cls.relationship} />}
              </div>
            </div>
            {email.recipient && (
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">To:</span>
                <span className="text-slate-700 truncate max-w-md">{email.recipient}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-500 font-medium">Received Date:</span>
              <span className="text-slate-700 font-semibold">
                {formatReceivedDateTime(email.received_at)}
              </span>
            </div>
            {email.has_attachments && (
              <div className="flex items-center space-x-1.5 text-indigo-600 font-medium pt-1 border-t border-slate-200">
                <Paperclip className="w-3.5 h-3.5" />
                <span>{email.attachment_count} Attachment(s) present</span>
              </div>
            )}
          </div>

          {/* Related Lead Card (Section 8 requirement) */}
          {leadTitle && (
            <div className="bg-gradient-to-r from-amber-50/60 to-white border border-amber-200 rounded-xl p-4 space-y-2 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-amber-900">
                  <Briefcase className="w-4 h-4 text-amber-600" />
                  <span className="text-xs font-bold uppercase tracking-wider">Associated Business Lead</span>
                </div>
                {leadStage && <Badge type="stage" value={leadStage} />}
              </div>
              <p className="text-xs font-semibold text-slate-800">{leadTitle}</p>
              {emailContext?.lead_business_context && (
                <p className="text-[11px] text-slate-600 line-clamp-2">{emailContext.lead_business_context}</p>
              )}
            </div>
          )}

          {/* Commercial Event Record Card */}
          {((email.commercial_events && email.commercial_events.length > 0) || (cls?.commercial_intent && cls.commercial_intent !== 'none')) && (
            <div className="bg-gradient-to-r from-teal-50/70 via-emerald-50/40 to-white border border-teal-200 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-teal-900 font-bold text-xs uppercase tracking-wider">
                  <Receipt className="w-4 h-4 text-teal-600" />
                  <span>Commercial Event & Accounts Record</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-100 text-teal-800">
                  {email.commercial_events?.[0]?.event_type?.replace(/_/g, ' ').toUpperCase() || cls?.commercial_intent?.replace(/_/g, ' ').toUpperCase() || 'COMMERCIAL RECORD'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
                {(email.commercial_events?.[0]?.reference_number || (email.commercial_events?.[0]?.raw_details?.po_number || email.commercial_events?.[0]?.raw_details?.utr_number)) && (
                  <div className="bg-white/80 p-2 rounded-lg border border-teal-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Reference #</span>
                    <span className="font-bold text-slate-800">
                      {email.commercial_events[0].reference_number || email.commercial_events[0].raw_details?.po_number || email.commercial_events[0].raw_details?.utr_number}
                    </span>
                  </div>
                )}
                {email.commercial_events?.[0]?.amount !== undefined && (
                  <div className="bg-white/80 p-2 rounded-lg border border-teal-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Amount</span>
                    <span className="font-bold text-slate-800">
                      ${email.commercial_events[0].amount.toLocaleString()} {email.commercial_events[0].currency || 'USD'}
                    </span>
                  </div>
                )}
                <div className="bg-white/80 p-2 rounded-lg border border-teal-100">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Accounts Status</span>
                  <span className="font-semibold text-emerald-700 capitalize">
                    {email.commercial_events?.[0]?.status?.replace(/_/g, ' ') || 'Action Queued'}
                  </span>
                </div>
              </div>

              {/* Explicit Verification / Disclaimer Box */}
              <div className="text-[11px] p-2.5 rounded-lg border bg-white/90 text-slate-600 leading-relaxed">
                {(cls?.commercial_intent === 'payment_remittance' || email.commercial_events?.[0]?.event_type === 'payment_remittance_received') && (
                  <span>
                    ⚠️ <strong>Remittance Advice:</strong> Recorded for tracking. This communication is not treated as verified payment confirmation until confirmed against bank ledger. Opportunity is not automatically marked Won.
                  </span>
                )}
                {(cls?.commercial_intent === 'purchase_order' || email.commercial_events?.[0]?.event_type === 'po_received') && (
                  <span>
                    📑 <strong>Purchase Order:</strong> Attached to opportunity. An invoice preparation task has been automatically queued for the Accounts team. Deal is not automatically marked Won solely on keyword presence.
                  </span>
                )}
                {(cls?.commercial_intent === 'payment_dispute' || email.commercial_events?.[0]?.event_type === 'payment_dispute_raised') && (
                  <span>
                    ⚖️ <strong>Billing Dispute:</strong> High-priority dispute ticket created for Accounts team to investigate discrepancy and reconcile statement with client.
                  </span>
                )}
                {(cls?.commercial_intent === 'invoice_request' || email.commercial_events?.[0]?.event_type === 'invoice_requested') && (
                  <span>
                    🧾 <strong>Invoice Request:</strong> Customer requested invoice/tax invoice. Queued for Accounts team fulfillment.
                  </span>
                )}
                {(cls?.commercial_intent === 'invoice_update' || email.commercial_events?.[0]?.event_type === 'invoice_update_requested') && (
                  <span>
                    ✏️ <strong>Invoice Update:</strong> Request for GST/address/line-item correction recorded for Accounts team processing.
                  </span>
                )}
              </div>
            </div>
          )}

          {/* AI Intelligence Card */}
          <div className="border border-indigo-100 bg-gradient-to-br from-indigo-50/50 via-white to-purple-50/30 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 bg-indigo-600 text-white rounded-lg">
                  <Sparkles className="w-4 h-4" />
                </div>
                <h4 className="font-bold text-slate-900 text-sm">Context-Aware AI Lead Intelligence</h4>
              </div>

              {cls && (
                <div className="flex items-center space-x-2">
                  <Badge type="classification" value={cls.pipeline_category || cls.intent} />
                  <button
                    onClick={() => setShowCorrectionForm(!showCorrectionForm)}
                    className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <Edit3 className="w-3 h-3" />
                    <span>Correct</span>
                  </button>
                </div>
              )}
            </div>

            {cls ? (
              <div className="space-y-4">
                {/* Executive Narrative Explanation */}
                {cls.executive_explanation && (
                  <div className="bg-gradient-to-r from-indigo-50/90 to-blue-50/90 rounded-xl p-4 border border-indigo-200 shadow-2xs space-y-2">
                    <div className="flex items-center space-x-1.5 text-indigo-950 font-bold text-xs uppercase tracking-wider">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Executive Intelligence & Business Opportunity Summary</span>
                    </div>
                    <p className="text-xs text-slate-800 leading-relaxed font-medium">
                      {cls.executive_explanation}
                    </p>
                  </div>
                )}

                {/* Priority, Qualification & Commercial Intent Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                  <div className="bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Priority</span>
                    <Badge type="priority" value={cls.priority_level || 'warm'} />
                  </div>
                  <div className="bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Urgency</span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                      cls.action_urgency === 'high' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                      cls.action_urgency === 'medium' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                      'bg-slate-50 text-slate-600 border border-slate-200'
                    }`}>
                      {cls.action_urgency ? `${cls.action_urgency.toUpperCase()} Urgency` : 'Medium'}
                    </span>
                  </div>
                  <div className="bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Business Potential</span>
                    <span className="text-xs font-semibold text-slate-700 capitalize">
                      {cls.business_potential || 'Medium'}
                    </span>
                  </div>
                  <div className="bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Commercial Intent</span>
                    {cls.commercial_intent && cls.commercial_intent !== 'none' ? (
                      <Badge type="commercial_intent" value={cls.commercial_intent} />
                    ) : (
                      <span className="text-xs text-slate-400">Standard</span>
                    )}
                  </div>
                </div>

                {/* Business Relevance & Pipeline */}
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Business Relevance</span>
                    {cls.relevance_category ? (
                      <Badge type="relevance" value={cls.relevance_category} />
                    ) : (
                      <Badge type="relevance" value={cls.is_business_relevant ? 'business_conversation' : 'system_notification'} />
                    )}
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Lead Pipeline</span>
                    {cls.pipeline_category ? (
                      <Badge type="pipeline" value={cls.pipeline_category} />
                    ) : (
                      <span className="text-xs text-slate-400 font-medium">Excluded from Pipelines</span>
                    )}
                  </div>
                </div>

                {cls.is_business_relevant === false && (
                  <div className="text-xs bg-slate-50 border border-slate-200 text-slate-600 rounded-lg p-3">
                    <span className="font-semibold text-slate-800 block mb-0.5">Non-Business Communication Filter:</span>
                    This email is classified as a non-business notification ({cls.relevance_category || 'system_notification'}). It is excluded from sales pipelines, lead conversions, and CRM contact creation.
                  </div>
                )}

                {/* 3 Taxonomy Dimensions */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Relationship</span>
                    <Badge type="relationship" value={cls.relationship} />
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Intent</span>
                    <Badge type="intent" value={cls.intent} />
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Lead Stage</span>
                    <Badge type="stage" value={cls.lead_stage} />
                  </div>
                </div>

                {/* Executive Classification Breakdown */}
                <div className="bg-white rounded-xl p-3.5 border border-indigo-200/80 shadow-xs space-y-2.5">
                  <div className="flex items-center space-x-1.5 text-indigo-900 font-bold text-xs uppercase tracking-wider">
                    <TrendingUp className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Executive Explanation: Why This Was Classified</span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="p-2.5 bg-indigo-50/50 rounded-lg border border-indigo-100">
                      <span className="font-bold text-indigo-950 block mb-0.5">
                        🎯 Why Stage is {cls.lead_stage.toUpperCase()}:
                      </span>
                      <p className="text-slate-600 leading-relaxed">
                        {cls.lead_stage === 'qualified' &&
                          'Confirmed commercial inquiry with explicit project scope, technical requirements, or budget allocation.'}
                        {cls.lead_stage === 'negotiation' &&
                          'Counter-offer or discount negotiation regarding proposal pricing or commercial terms.'}
                        {cls.lead_stage === 'new' &&
                          'First-time inbound business communication seeking service information or quotation.'}
                        {cls.lead_stage === 'won' &&
                          'Formal purchase order received or contract signed by customer.'}
                        {(cls.lead_stage === 'unknown' || cls.lead_stage === 'not_applicable') &&
                          (!cls.is_business_relevant
                            ? 'This email is a non-business automated notification. Sales stages only apply to legitimate business leads and are intentionally excluded.'
                            : 'Lacks specific commercial requirements or budget signals needed to advance lead stage.')}
                        {!['qualified', 'negotiation', 'new', 'won', 'unknown', 'not_applicable'].includes(cls.lead_stage) &&
                          cls.classification_reason}
                      </p>
                    </div>

                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                      <span className="font-bold text-slate-800 block mb-0.5">
                        💼 Commercial Relevance:
                      </span>
                      <p className="text-slate-600 leading-relaxed">
                        {cls.is_business_relevant
                          ? `Classified as ${cls.relevance_category?.replace('_', ' ') || 'business communication'}. Directly impacts pipeline.`
                          : `Classified as ${cls.relevance_category?.replace('_', ' ') || 'non-business notification'}. Isolated from CRM.`}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Classification Reason */}
                {cls.classification_reason && (
                  <div className="text-xs bg-white/80 p-3 rounded-lg border border-slate-200">
                    <span className="font-semibold text-slate-700 block mb-1">Classification Explanation:</span>
                    <p className="text-slate-600 leading-relaxed">{cls.classification_reason}</p>
                  </div>
                )}

                {/* Context Used From Conversation (Section 8 requirement) */}
                {contextUsed && (
                  <div className="text-xs bg-blue-50/80 p-3 rounded-lg border border-blue-200 text-blue-900">
                    <div className="flex items-center space-x-1.5 font-bold mb-1 text-blue-800">
                      <GitBranch className="w-3.5 h-3.5 text-blue-600" />
                      <span>Context Used From Previous Conversation:</span>
                    </div>
                    <p className="text-blue-700 leading-relaxed">{contextUsed}</p>
                  </div>
                )}

                {/* Supporting Evidence */}
                {cls.supporting_evidence && cls.supporting_evidence.length > 0 && (
                  <div>
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
                      Supporting Evidence:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {cls.supporting_evidence.map((ev, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-700 font-medium">
                          {ev}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Signals */}
                {cls.key_signals && cls.key_signals.length > 0 && (
                  <div>
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
                      Key Signals Detected:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {cls.key_signals.map((sig, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-white border border-slate-200 text-slate-700">
                          {sig}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggested Next Action */}
                {cls.suggested_next_action && (
                  <div className="flex items-start space-x-2.5 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg p-3 text-xs">
                    <ArrowRight className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">Recommended Next Action:</span>
                      <p className="mt-0.5">{cls.suggested_next_action}</p>
                    </div>
                  </div>
                )}

                {/* Human Review Status */}
                {cls.requires_human_review && (
                  <div className="flex items-center space-x-2 text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2.5 text-xs font-semibold">
                    <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    <span>Review recommended or confidence threshold below 85%. Needs human verification.</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-4 space-y-3">
                <p className="text-xs text-slate-600">This email has not been classified by the AI pipeline yet.</p>
                <button
                  onClick={handleClassifyNow}
                  disabled={classifying}
                  className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${classifying ? 'animate-spin' : ''}`} />
                  <span>{classifying ? 'Classifying Email...' : 'Run AI Classification'}</span>
                </button>
              </div>
            )}
          </div>

          {/* AI Industry Classification Card (Section 8A requirement) */}
          {cls && (
            <div className="border border-blue-100 bg-gradient-to-br from-blue-50/40 via-white to-sky-50/30 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="p-1.5 bg-blue-600 text-white rounded-lg">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <h4 className="font-bold text-slate-900 text-sm">AI Industry Classification</h4>
                </div>
                {cls.industry_confidence !== undefined && (
                  <Badge type="confidence" value={cls.industry_confidence} />
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 pt-1">
                <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Customer Org Industry</span>
                  <Badge type="industry" value={cls.customer_org_industry || cls.sender_industry || 'Unknown'} />
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Requested Solution Domain</span>
                  <Badge type="industry" value={cls.requested_solution_domain || cls.target_industry || 'Unknown'} />
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Sub-Industry</span>
                  <span className="text-xs font-semibold text-slate-800 truncate block">
                    {cls.sub_industry || '-'}
                  </span>
                </div>
              </div>

              {cls.business_activity && (
                <div className="text-xs bg-white/80 p-3 rounded-lg border border-slate-200">
                  <span className="font-semibold text-slate-700 block mb-1">Business Activity:</span>
                  <p className="text-slate-600 leading-relaxed">{cls.business_activity}</p>
                </div>
              )}

              {cls.industry_reason && (
                <div className="text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="font-semibold text-slate-700 block mb-1">Industry Explanation:</span>
                  <p className="text-slate-600 leading-relaxed">{cls.industry_reason}</p>
                </div>
              )}

              {cls.industry_evidence && cls.industry_evidence.length > 0 && (
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
                    Industry Evidence:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {cls.industry_evidence.map((ev, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-blue-50/70 border border-blue-200 text-blue-700 font-medium">
                        {ev}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Actionable Next Tasks (Interactive checklist) */}
          {((email.tasks && email.tasks.length > 0) || cls?.suggested_next_action) && (
            <div className="bg-white border border-emerald-200 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-emerald-900 font-bold text-xs uppercase tracking-wider">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  <span>Actionable Follow-up Tasks</span>
                </div>
                {email.tasks && email.tasks.length > 0 && (
                  <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                    {email.tasks.filter((t) => t.status === 'completed').length}/{email.tasks.length} Done
                  </span>
                )}
              </div>

              {email.tasks && email.tasks.length > 0 ? (
                <div className="space-y-2">
                  {email.tasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={async () => {
                        const newStatus = task.status === 'completed' ? 'pending' : 'completed';
                        await api.updateTask(task.id, { status: newStatus });
                        onUpdated();
                      }}
                      className={`flex items-start space-x-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                        task.status === 'completed'
                          ? 'bg-slate-50 border-slate-200 text-slate-400 line-through'
                          : 'bg-emerald-50/40 border-emerald-200 text-slate-800 hover:bg-emerald-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={task.status === 'completed'}
                        readOnly
                        className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                      />
                      <div className="flex-1 text-xs">
                        <span className="font-semibold">{task.title}</span>
                        {task.assigned_to && (
                          <span className="ml-2 text-[10px] text-slate-500 font-normal">
                            Assigned: {task.assigned_to}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                cls?.suggested_next_action && (
                  <div className="text-xs bg-emerald-50 p-2.5 rounded-lg border border-emerald-200 text-emerald-900 font-medium">
                    {cls.suggested_next_action}
                  </div>
                )
              )}
            </div>
          )}

          {/* Manual Correction Form Drawer */}
          {showCorrectionForm && (
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
              <h5 className="font-bold text-xs text-slate-800 uppercase tracking-wider">Manual Classification Correction</h5>

              {/* Relevance & Pipeline Controls */}
              <div className="grid grid-cols-3 gap-3 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Business Relevant?</label>
                  <select
                    value={corrIsBiz ? 'true' : 'false'}
                    onChange={(e) => setCorrIsBiz(e.target.value === 'true')}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    <option value="true">Yes (Business Lead/Comms)</option>
                    <option value="false">No (System/Alert/Newsletter)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Relevance Category</label>
                  <select
                    value={corrRelevance}
                    onChange={(e) => setCorrRelevance(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    <option value="business_enquiry">Business Enquiry</option>
                    <option value="business_conversation">Business Conversation</option>
                    <option value="customer_support">Customer Support</option>
                    <option value="purchase_commercial">Purchase / Commercial</option>
                    <option value="internal_communication">Internal Communication</option>
                    <option value="account_security_notification">Security Notification</option>
                    <option value="system_notification">System Notification</option>
                    <option value="automated_notification">Automated Notification</option>
                    <option value="newsletter_marketing">Newsletter / Marketing</option>
                    <option value="spam_irrelevant">Spam / Irrelevant</option>
                    <option value="unknown_review">Unknown / Review</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Pipeline Category</label>
                  <select
                    value={corrPipeline}
                    onChange={(e) => setCorrPipeline(e.target.value)}
                    disabled={!corrIsBiz}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white disabled:opacity-50"
                  >
                    <option value="new_leads">New Leads</option>
                    <option value="negotiations">Negotiations</option>
                    <option value="follow_ups">Follow-ups</option>
                    <option value="clarifications">Clarifications</option>
                    <option value="existing_leads">Existing Leads</option>
                    <option value="purchase_orders">Purchase Orders</option>
                    <option value="invoice_request">Invoice Request</option>
                    <option value="invoice_update">Invoice Update</option>
                    <option value="payment_remittance">Payment Remittance</option>
                    <option value="payment_follow_up">Payment Follow-up</option>
                    <option value="payment_dispute">Payment Dispute</option>
                    <option value="invoices">Invoices (General)</option>
                    <option value="needs_review">Needs Review</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Relationship</label>
                  <select
                    value={corrRelationship}
                    onChange={(e) => setCorrRelationship(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    <option value="new_contact">New Contact</option>
                    <option value="existing_lead">Existing Lead</option>
                    <option value="existing_customer">Existing Customer</option>
                    <option value="unknown">Unknown</option>
                    <option value="not_applicable">Not Applicable</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Intent</label>
                  <select
                    value={corrIntent}
                    onChange={(e) => setCorrIntent(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    <option value="new_enquiry">New Enquiry</option>
                    <option value="negotiation">Negotiation</option>
                    <option value="follow_up">Follow-up</option>
                    <option value="business_clarification">Clarification</option>
                    <option value="purchase_order">Purchase Order</option>
                    <option value="invoice_request">Invoice Request</option>
                    <option value="invoice_update">Invoice Update</option>
                    <option value="payment_remittance">Payment Remittance</option>
                    <option value="payment_follow_up">Payment Follow-up</option>
                    <option value="payment_dispute">Payment Dispute</option>
                    <option value="invoice">Invoice (General)</option>
                    <option value="complaint">Complaint</option>
                    <option value="other">Other / Noise</option>
                    <option value="not_applicable">Not Applicable</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Lead Stage</label>
                  <select
                    value={corrStage}
                    onChange={(e) => setCorrStage(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    <option value="new">New</option>
                    <option value="qualified">Qualified</option>
                    <option value="proposal_sent">Proposal Sent</option>
                    <option value="negotiation">Negotiation</option>
                    <option value="won">Won</option>
                    <option value="lost">Lost</option>
                    <option value="unknown">Unknown</option>
                    <option value="not_applicable">Not Applicable</option>
                  </select>
                </div>
              </div>

              {/* Industry Correction Controls (Section 8E requirement) */}
              <div className="grid grid-cols-3 gap-3 pt-1">
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Sender Industry</label>
                  <select
                    value={corrSenderIndustry}
                    onChange={(e) => setCorrSenderIndustry(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    {Object.keys(taxonomy).length > 0 ? (
                      Object.keys(taxonomy).map((ind) => (
                        <option key={ind} value={ind}>{ind}</option>
                      ))
                    ) : (
                      <>
                        <option value="IT & Software">IT & Software</option>
                        <option value="Healthcare">Healthcare</option>
                        <option value="Manufacturing">Manufacturing</option>
                        <option value="Banking & Finance">Banking & Finance</option>
                        <option value="Retail & E-commerce">Retail & E-commerce</option>
                        <option value="Education">Education</option>
                        <option value="Hospitality & Tourism">Hospitality & Tourism</option>
                        <option value="Other">Other</option>
                        <option value="Unknown">Unknown</option>
                      </>
                    )}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Target Industry</label>
                  <select
                    value={corrTargetIndustry}
                    onChange={(e) => setCorrTargetIndustry(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white"
                  >
                    {Object.keys(taxonomy).length > 0 ? (
                      Object.keys(taxonomy).map((ind) => (
                        <option key={ind} value={ind}>{ind}</option>
                      ))
                    ) : (
                      <>
                        <option value="IT & Software">IT & Software</option>
                        <option value="Healthcare">Healthcare</option>
                        <option value="Manufacturing">Manufacturing</option>
                        <option value="Banking & Finance">Banking & Finance</option>
                        <option value="Retail & E-commerce">Retail & E-commerce</option>
                        <option value="Education">Education</option>
                        <option value="Hospitality & Tourism">Hospitality & Tourism</option>
                        <option value="Other">Other</option>
                        <option value="Unknown">Unknown</option>
                      </>
                    )}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Sub-Industry</label>
                  <input
                    type="text"
                    placeholder="e.g. Healthcare Technology"
                    value={corrSubIndustry}
                    onChange={(e) => setCorrSubIndustry(e.target.value)}
                    className="w-full text-xs border border-slate-300 rounded-lg p-2"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-600 block mb-1">Correction Notes (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Customer approved revised quotation"
                  value={corrNotes}
                  onChange={(e) => setCorrNotes(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  onClick={() => setShowCorrectionForm(false)}
                  className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveCorrection}
                  disabled={savingCorrection}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50"
                >
                  {savingCorrection ? 'Saving...' : 'Save Correction'}
                </button>
              </div>
            </div>
          )}

          {/* Audit & Classification History Section (Section 8 requirement) */}
          {auditHistory.length > 0 && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center space-x-2 text-slate-700">
                <History className="w-4 h-4 text-indigo-600" />
                <h5 className="font-bold text-xs uppercase tracking-wider">
                  Classification History & Audit Trail ({auditHistory.length})
                </h5>
              </div>
              <div className="space-y-2">
                {auditHistory.map((item) => (
                  <div key={item.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between items-center text-[10px] text-slate-500">
                      <span className="font-semibold text-slate-700">Corrected by: {item.corrected_by}</span>
                      <span>{formatReceivedDateTime(item.corrected_at)}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-[11px]">
                      <span className="text-slate-500 line-through">
                        {item.previous_values?.relationship} / {item.previous_values?.intent} / {item.previous_values?.lead_stage}
                      </span>
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                      <span className="font-semibold text-indigo-700">
                        {item.corrected_values?.relationship} / {item.corrected_values?.intent} / {item.corrected_values?.lead_stage}
                      </span>
                    </div>
                    {item.notes && <p className="text-[11px] text-slate-600 italic">"{item.notes}"</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Email Body */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">Message Content</span>
            <div className="bg-slate-50 rounded-xl p-5 border border-slate-200 text-xs text-slate-800 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto selection:bg-indigo-200">
              {email.body_text || email.snippet || '(No content available)'}
            </div>
          </div>

          {/* Conversation History Timeline (Section 8 requirement) */}
          {((emailContext?.prior_emails && emailContext.prior_emails.length > 0) || threadEmails.length > 1) && (
            <div className="space-y-3 pt-4 border-t border-slate-200">
              <div className="flex items-center space-x-2">
                <MessageSquare className="w-4 h-4 text-slate-600" />
                <h5 className="font-bold text-xs text-slate-800 uppercase tracking-wider">
                  Conversation & Sender History Timeline
                </h5>
              </div>
              <div className="space-y-2.5">
                {(emailContext?.prior_emails || []).map((prior) => (
                  <div
                    key={`prior-${prior.id}`}
                    className={`p-3 rounded-lg border text-xs ${
                      prior.id === email.id
                        ? 'bg-indigo-50 border-indigo-200 ring-1 ring-indigo-200'
                        : 'bg-white border-slate-200'
                    }`}
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-slate-800 truncate max-w-sm">{prior.sender}</span>
                      <span className="text-slate-500 text-[10px]">
                        {formatReceivedDateTime(prior.received_at)}
                      </span>
                    </div>
                    <p className="font-medium text-slate-700 truncate">{prior.subject}</p>
                    <p className="text-slate-500 text-[11px] line-clamp-2 mt-0.5">{prior.snippet}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
