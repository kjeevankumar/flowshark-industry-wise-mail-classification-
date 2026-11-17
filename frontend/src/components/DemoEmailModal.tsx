import React, { useEffect, useState } from 'react';
import {
  X,
  Sparkles,
  Send,
  Play,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Briefcase,
  HelpCircle,
  TrendingUp,
  Tag,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { Badge } from './Badge';
import { api } from '../services/api';

interface DemoEmailModalProps {
  isOpen: boolean;
  onClose: () => void;
  onEmailInjected: () => void;
}

export const DemoEmailModal: React.FC<DemoEmailModalProps> = ({
  isOpen,
  onClose,
  onEmailInjected,
}) => {
  const [presets, setPresets] = useState<Record<string, any>>({});
  const [selectedPresetKey, setSelectedPresetKey] = useState<string>('qualified_lead');
  const [sender, setSender] = useState<string>('');
  const [subject, setSubject] = useState<string>('');
  const [body, setBody] = useState<string>('');
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [injecting, setInjecting] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPresets();
    }
  }, [isOpen]);

  const loadPresets = async () => {
    try {
      setLoadingPresets(true);
      const res = await api.getDemoPresets();
      setPresets(res.presets);
      if (res.presets.qualified_lead) {
        applyPreset(res.presets.qualified_lead, 'qualified_lead');
      }
    } catch (err) {
      console.error('Failed to load demo presets:', err);
    } finally {
      setLoadingPresets(false);
    }
  };

  const applyPreset = (preset: any, key: string) => {
    setSelectedPresetKey(key);
    setSender(preset.sender);
    setSubject(preset.subject);
    setBody(preset.body);
    setResult(null);
    setErrorMsg(null);
  };

  const handleSimulate = async () => {
    try {
      setSimulating(true);
      setErrorMsg(null);
      const data = await api.simulateDemoEmail({
        sender,
        subject,
        body,
        inject_into_inbox: false,
      });
      setResult(data);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  const handleInjectIntoInbox = async () => {
    try {
      setInjecting(true);
      setErrorMsg(null);
      const data = await api.simulateDemoEmail({
        sender,
        subject,
        body,
        inject_into_inbox: true,
      });
      setResult(data);
      setSuccessToast('Email successfully ingested and classified into your FlowShark Inbox!');
      onEmailInjected();
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Ingestion failed');
    } finally {
      setInjecting(false);
    }
  };

  if (!isOpen) return null;

  const c = result?.classification;
  const exp = result?.executive_breakdown;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
              <Sparkles className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <span>AI Email Classification Demo & Tester</span>
                <span className="text-[10px] uppercase font-extrabold tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 px-2 py-0.5 rounded-full">
                  Live Engine
                </span>
              </h3>
              <p className="text-xs text-slate-300">
                Test and verify how FlowShark classifies B2B leads, negotiations, existing leads, and filters system noise
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Preset Buttons */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              1. Choose a Demo Scenario Preset:
            </span>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {Object.entries(presets).map(([key, p]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => applyPreset(p, key)}
                  className={`p-2.5 rounded-xl border text-left transition-all flex flex-col justify-between ${
                    selectedPresetKey === key
                      ? 'bg-indigo-50 border-indigo-400 ring-2 ring-indigo-200 shadow-sm'
                      : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <span className="text-xs font-bold text-slate-800 line-clamp-1">{p.label.split('(')[0]}</span>
                  <span className="text-[10px] text-slate-500 mt-1 line-clamp-1">
                    {key === 'qualified_lead' && '🎯 $75k Budget Approved'}
                    {key === 'negotiation' && '🤝 15% Price Discount'}
                    {key === 'new_lead' && '🚀 First-time Inquiry'}
                    {key === 'existing_lead' && '🔄 Scope Follow-up'}
                    {key === 'security_alert' && '🛡️ Google Security'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Input Fields */}
          <div className="bg-slate-50/70 rounded-xl p-4 border border-slate-200 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block mb-1">
                  Sender (From)
                </label>
                <input
                  type="text"
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-white font-mono"
                  placeholder="e.g. client@company.com"
                />
              </div>
              <div>
                <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block mb-1">
                  Subject Line
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-white font-medium"
                  placeholder="e.g. Inquiry regarding services"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block mb-1">
                Email Message Body
              </label>
              <textarea
                rows={4}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="w-full text-xs border border-slate-300 rounded-lg p-2.5 bg-white font-mono leading-relaxed"
                placeholder="Type or paste email body content to test..."
              />
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-[11px] text-slate-500">
                You can edit the text above freely to test any custom email phrase or scenario.
              </span>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handleSimulate}
                  disabled={simulating || injecting || !body.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <Play className={`w-3.5 h-3.5 ${simulating ? 'animate-spin' : ''}`} />
                  <span>{simulating ? 'Analyzing...' : 'Simulate & Explain'}</span>
                </button>
                <button
                  type="button"
                  onClick={handleInjectIntoInbox}
                  disabled={simulating || injecting || !body.trim()}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <Send className={`w-3.5 h-3.5 ${injecting ? 'animate-spin' : ''}`} />
                  <span>{injecting ? 'Injecting...' : 'Inject & Save to Inbox'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Feedback messages */}
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successToast && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center space-x-2 animate-bounce">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span className="font-semibold">{successToast}</span>
            </div>
          )}

          {/* Classification Results & Executive Explanation */}
          {result && c && (
            <div className="border border-indigo-100 bg-gradient-to-br from-indigo-50/40 via-white to-purple-50/20 rounded-2xl p-5 shadow-sm space-y-5 animate-in fade-in duration-300">
              <div className="flex items-center justify-between border-b border-indigo-100/60 pb-3">
                <div className="flex items-center space-x-2">
                  <div className="p-1.5 bg-indigo-600 text-white rounded-lg">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">Classification Decision & Reasoning</h4>
                    <span className="text-[11px] text-slate-500">
                      Evaluated via Multi-Signal Hybrid Engine (Relevance + Rule Signals + Pipeline + Industry)
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge type="confidence" value={c.confidence} />
                  {result.is_injected && (
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      Saved in Inbox (ID: {result.email_id})
                    </span>
                  )}
                </div>
              </div>

              {/* Status Badges Matrix */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Relevance</span>
                  <Badge type="relevance" value={c.relevance_category} />
                </div>
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Lead Pipeline</span>
                  {c.pipeline_category ? (
                    <Badge type="pipeline" value={c.pipeline_category} />
                  ) : (
                    <span className="text-xs text-slate-400 font-medium">Excluded from Pipelines</span>
                  )}
                </div>
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Lead Stage</span>
                  <Badge type="stage" value={c.lead_stage} />
                </div>
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Target Industry</span>
                  <Badge type="industry" value={c.target_industry || 'Unknown'} />
                </div>
              </div>

              {/* Executive Breakdown Card (Answers "Why Qualified?", "Why Unknown?", etc.) */}
              {exp && (
                <div className="bg-white rounded-xl p-4 border border-indigo-200 shadow-xs space-y-3">
                  <div className="flex items-center space-x-2 text-indigo-900 font-bold text-xs uppercase tracking-wider">
                    <TrendingUp className="w-4 h-4 text-indigo-600" />
                    <span>Executive Explanation: Why This Email Was Classified</span>
                  </div>

                  <div className="space-y-2.5 text-xs text-slate-700">
                    {/* Why Lead Stage */}
                    <div className="p-3 bg-indigo-50/60 border border-indigo-100 rounded-lg">
                      <span className="font-bold text-indigo-950 block mb-0.5">🎯 Lead Stage Rationale:</span>
                      <p className="text-slate-700 leading-relaxed">{exp.why_lead_stage}</p>
                    </div>

                    {/* Why Business Relevance */}
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                      <span className="font-bold text-slate-900 block mb-0.5">💼 Commercial Relevance:</span>
                      <p className="text-slate-600 leading-relaxed">{exp.why_relevance}</p>
                    </div>

                    {/* Why Industry */}
                    <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-lg">
                      <span className="font-bold text-blue-950 block mb-0.5">🏢 Industry Rationale:</span>
                      <p className="text-blue-800 leading-relaxed">{exp.why_industry}</p>
                    </div>

                    {/* Key Signals & Evidence Chips */}
                    {exp.key_signals && exp.key_signals.length > 0 && (
                      <div className="pt-1">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1.5">
                          Extracted Signals & Evidence:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {exp.key_signals.map((sig: string, i: number) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded-md bg-indigo-100/70 border border-indigo-200 text-indigo-800 font-medium text-[11px]"
                            >
                              {sig}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
