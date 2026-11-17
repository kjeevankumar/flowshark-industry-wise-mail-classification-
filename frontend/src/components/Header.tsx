import React, { useState, useRef, useEffect } from 'react';
import { RefreshCw, Zap, CheckCircle2, AlertCircle, Mail, ChevronDown, Check, Plus } from 'lucide-react';
import { ConnectionDetailsResponse, DashboardSummary, SyncStatus } from '../types';
import { api } from '../services/api';
import { formatSyncTimeAgo } from '../utils/dateUtils';

interface HeaderProps {
  title: string;
  subtitle?: string;
  summary: DashboardSummary | null;
  syncStatus: SyncStatus | null;
  connectionDetails: ConnectionDetailsResponse | null;
  onRefresh: () => void;
  onSwitchMailbox: (mailboxId: number) => Promise<void>;
  onNavigateToConnection: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  summary,
  syncStatus,
  connectionDetails,
  onRefresh,
  onSwitchMailbox,
  onNavigateToConnection,
}) => {
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [switchingId, setSwitchingId] = useState<number | null>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSync = async () => {
    try {
      setSyncing(true);
      setSyncMessage('Connecting to Gmail IMAP...');
      const res = await api.triggerSync(50);
      setSyncMessage(res.message);
      onRefresh();
      setTimeout(() => setSyncMessage(null), 4000);
    } catch (err: any) {
      setSyncMessage('Sync failed: ' + (err.response?.data?.detail || err.message));
      setTimeout(() => setSyncMessage(null), 5000);
    } finally {
      setSyncing(false);
    }
  };

  const handleSelectMailbox = async (mailboxId: number) => {
    if (mailboxId === connectionDetails?.active_mailbox_id) {
      setIsDropdownOpen(false);
      return;
    }
    try {
      setSwitchingId(mailboxId);
      await onSwitchMailbox(mailboxId);
      setIsDropdownOpen(false);
    } catch (err) {
      console.error('Failed to switch mailbox:', err);
    } finally {
      setSwitchingId(null);
    }
  };

  const formatLastSync = (timestamp?: string) => {
    return formatSyncTimeAgo(timestamp);
  };

  const isSyncActive = syncing || syncStatus?.worker_status === 'syncing';
  const hasError = syncStatus?.connection_status === 'error' || syncStatus?.worker_status === 'error';
  const activeEmail = connectionDetails?.email_address || summary?.active_mailbox_email || syncStatus?.account_email;

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      <div className="flex items-center space-x-4">
        <div>
          <h2 className="text-lg font-bold text-slate-800 leading-tight">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>

        {/* Global Active Mailbox Switcher Pill */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-slate-50 transition-all text-xs font-semibold text-slate-700 bg-white shadow-xs"
            title="Click to switch active Gmail account"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <Mail className="w-3.5 h-3.5 text-indigo-600" />
            <span className="max-w-[180px] truncate">
              {activeEmail || 'Select Mailbox'}
            </span>
            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Mailbox Selector Dropdown */}
          {isDropdownOpen && (
            <div className="absolute left-0 mt-1.5 w-72 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="px-3 py-1.5 border-b border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <span>Switch Active Mailbox</span>
                <span>{connectionDetails?.available_mailboxes?.length || 0} Accounts</span>
              </div>

              <div className="max-h-60 overflow-y-auto py-1">
                {connectionDetails?.available_mailboxes && connectionDetails.available_mailboxes.length > 0 ? (
                  connectionDetails.available_mailboxes.map((mb) => {
                    const isActive = mb.id === connectionDetails.active_mailbox_id;
                    const isSwitching = switchingId === mb.id;
                    return (
                      <button
                        key={mb.id}
                        onClick={() => handleSelectMailbox(mb.id)}
                        disabled={isSwitching}
                        className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-slate-50 transition-colors ${
                          isActive ? 'bg-indigo-50/50' : ''
                        }`}
                      >
                        <div className="flex items-center space-x-2.5 overflow-hidden">
                          <div className={`p-1.5 rounded-lg ${isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                            {isSwitching ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Mail className="w-3.5 h-3.5" />
                            )}
                          </div>
                          <div className="overflow-hidden">
                            <p className={`text-xs font-semibold truncate ${isActive ? 'text-indigo-900' : 'text-slate-800'}`}>
                              {mb.email_address}
                            </p>
                            <p className="text-[10px] text-slate-400">
                              {mb.total_emails_stored} emails stored
                            </p>
                          </div>
                        </div>

                        {isActive && (
                          <span className="flex items-center text-[10px] font-bold text-indigo-600 bg-indigo-100/70 px-2 py-0.5 rounded-full">
                            Active
                          </span>
                        )}
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-3 text-center text-xs text-slate-500">
                    No accounts connected yet.
                  </div>
                )}
              </div>

              <div className="border-t border-slate-100 pt-1 mt-1 px-1.5">
                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    onNavigateToConnection();
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg text-left text-xs font-semibold text-indigo-600 hover:bg-indigo-50 flex items-center space-x-2 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Connect or Manage Accounts</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-3">
        {syncMessage && (
          <span className="text-xs font-medium text-slate-600 bg-slate-100 px-3 py-1 rounded-full border border-slate-200 animate-fade-in">
            {syncMessage}
          </span>
        )}

        {/* Live Automatic Synchronization Status Pill */}
        <div
          className={`flex items-center space-x-2 px-3 py-1 rounded-full border text-xs font-medium transition-all ${
            hasError
              ? 'bg-rose-50 border-rose-200 text-rose-700'
              : isSyncActive
              ? 'bg-blue-50 border-blue-200 text-blue-700 animate-pulse'
              : 'bg-emerald-50 border-emerald-200 text-emerald-700'
          }`}
          title={syncStatus?.latest_sync_error || `Auto-Sync running every ${syncStatus?.sync_interval_seconds || 30}s`}
        >
          {hasError ? (
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
          ) : isSyncActive ? (
            <RefreshCw className="w-3.5 h-3.5 text-blue-600 animate-spin" />
          ) : (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          )}
          <span>
            {hasError
              ? 'Sync Error'
              : isSyncActive
              ? 'Syncing Gmail...'
              : 'Auto-Sync Active'}
          </span>
          {syncStatus?.last_successful_sync && !isSyncActive && (
            <span className="text-slate-400 border-l border-emerald-200 pl-1.5 font-normal">
              {formatLastSync(syncStatus.last_successful_sync)}
            </span>
          )}
        </div>

        {/* Latest Sync New Emails Badge */}
        {syncStatus && syncStatus.new_emails_retrieved_latest_sync > 0 && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300 animate-bounce">
            +{syncStatus.new_emails_retrieved_latest_sync} new
          </span>
        )}

        {/* AI Provider Status Pill */}
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs">
          <Zap className={`w-3.5 h-3.5 ${summary?.is_llm_active ? 'text-indigo-600 fill-indigo-600' : 'text-amber-500 fill-amber-500'}`} />
          <span className="text-slate-700 font-medium capitalize">
            {summary?.active_llm_provider || 'Hybrid AI'}
          </span>
        </div>

        {/* Quick Sync Button */}
        <button
          onClick={handleSync}
          disabled={isSyncActive}
          className="inline-flex items-center space-x-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSyncActive ? 'animate-spin' : ''}`} />
          <span>{isSyncActive ? 'Syncing...' : 'Sync Now'}</span>
        </button>

        {/* Refresh UI Data */}
        <button
          onClick={onRefresh}
          title="Refresh Dashboard Data"
          className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
