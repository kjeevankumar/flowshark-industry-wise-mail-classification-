import React, { useEffect, useState } from 'react';
import {
  Cpu,
  Shield,
  BarChart3,
  CheckCircle,
  AlertCircle,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    try {
      setLoadingMetrics(true);
      const res = await api.getMetrics();
      setMetrics(res);
    } catch (err) {
      console.error('Failed to load metrics:', err);
    } finally {
      setLoadingMetrics(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">AI Model Configuration & Evaluation</h2>
        <p className="text-xs text-slate-500">
          Inspect LLM provider bindings, confidence calibration thresholds, and classification performance.
        </p>
      </div>

      {/* AI Provider Overview */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-xl">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-base text-slate-900">LLM Semantic Classification Engine</h3>
            <p className="text-xs text-slate-500">Hybrid rule-based NLP + Large Language Model integration</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 pt-2 text-xs">
          <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200">
            <span className="font-semibold text-slate-500 block mb-1">Supported Providers</span>
            <span className="font-bold text-slate-800">Google Gemini / OpenAI / Rule Fallback</span>
          </div>
          <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200">
            <span className="font-semibold text-slate-500 block mb-1">Active Architecture</span>
            <span className="font-bold text-indigo-600">Hybrid 3-Stage Pipeline</span>
          </div>
          <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200">
            <span className="font-semibold text-slate-500 block mb-1">Prompt Injection Defense</span>
            <span className="font-bold text-emerald-600">Strict Delineation & Isolation</span>
          </div>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 space-y-1">
          <p className="font-bold">Configuring an External LLM Provider Key:</p>
          <p className="leading-relaxed">
            To enable deep semantic understanding with Gemini or OpenAI, add your API key to your local <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">.env</code> file:
            <br />
            <code className="block mt-1 bg-amber-100/70 p-2 rounded font-mono text-[11px]">
              LLM_PROVIDER=gemini<br />
              GEMINI_API_KEY=your_gemini_api_key_here
            </code>
            When no key is configured, FlowShark operates seamlessly on its high-precision rule-based signal detector and NLP preprocessor.
          </p>
        </div>
      </div>

      {/* Confidence Thresholds */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
        <h3 className="font-bold text-sm text-slate-900">Confidence Calibration & Review Heuristics</h3>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl space-y-1">
            <span className="font-bold text-emerald-800 text-sm">&ge; 85% Confidence</span>
            <p className="text-emerald-700 font-semibold">High Confidence</p>
            <p className="text-emerald-600 text-[11px]">Automatically accepted and assigned to pipeline categories without review flag.</p>
          </div>
          <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl space-y-1">
            <span className="font-bold text-amber-800 text-sm">60% - 84% Confidence</span>
            <p className="text-amber-700 font-semibold">Medium Confidence</p>
            <p className="text-amber-600 text-[11px]">Displays predicted category with informational review badge.</p>
          </div>
          <div className="bg-rose-50 border border-rose-200 p-4 rounded-xl space-y-1">
            <span className="font-bold text-rose-800 text-sm">&lt; 60% or Contradictory</span>
            <p className="text-rose-700 font-semibold">Low Confidence</p>
            <p className="text-rose-600 text-[11px]">Marked as Needs Review for human validation and correction.</p>
          </div>
        </div>
      </div>

      {/* Database Classification Metrics */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-sm text-slate-900">Live Database Classification Statistics</h3>
          </div>
          <button
            onClick={loadMetrics}
            disabled={loadingMetrics}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            <RefreshCw className={`w-4 h-4 ${loadingMetrics ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {metrics ? (
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 font-medium block">Total Classified</span>
              <span className="text-lg font-bold text-slate-900">{metrics.total_classified}</span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 font-medium block">Flagged For Review</span>
              <span className="text-lg font-bold text-rose-600">{metrics.needs_review_count}</span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-100">
              <span className="text-slate-500 font-medium block">Human Corrections Logged</span>
              <span className="text-lg font-bold text-indigo-600">{metrics.human_corrections_count}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">Loading metrics...</p>
        )}
      </div>
    </div>
  );
};

