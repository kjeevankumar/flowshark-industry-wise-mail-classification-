import React, { useEffect, useState } from 'react';
import {
  Mail,
  ShieldCheck,
  Server,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Database,
  ArrowRight,
  Plus,
  Key,
  Eye,
  EyeOff,
  Check,
  Globe,
  Settings2,
} from 'lucide-react';
import { ConfigStatus, ConnectionDetailsResponse, SyncStatus, UpdateConnectionRequest } from '../types';
import { api } from '../services/api';
import { formatReceivedDateTime, formatSyncTimeAgo } from '../utils/dateUtils';

interface ConnectionPageProps {
  onRefreshSummary: () => void;
  onMailboxSwitched?: () => void;
}

export const ConnectionPage: React.FC<ConnectionPageProps> = ({ onRefreshSummary, onMailboxSwitched }) => {
  const [connectionDetails, setConnectionDetails] = useState<ConnectionDetailsResponse | null>(null);
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // New Connection Form
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [imapHost, setImapHost] = useState('imap.gmail.com');
  const [imapPort, setImapPort] = useState(993);
  const [smtpHost, setSmtpHost] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);

  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connectSuccess, setConnectSuccess] = useState<string | null>(null);

  // Switching state
  const [switchingId, setSwitchingId] = useState<number | null>(null);

  // Protocol test states
  const [testingImap, setTestingImap] = useState(false);
  const [imapResult, setImapResult] = useState<any>(null);

  const [testingSmtp, setTestingSmtp] = useState(false);
  const [smtpResult, setSmtpResult] = useState<any>(null);

  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);

  useEffect(() => {
    loadAllStatus();
  }, []);

  const loadAllStatus = async () => {
    try {
      setLoading(true);
      const [conn, conf, sync] = await Promise.all([
        api.getConnectionDetails(),
        api.getConfigStatus(),
        api.getSyncStatus(),
      ]);
      setConnectionDetails(conn);
      setConfig(conf);
      setSyncStatus(sync);
    } catch (err) {
      console.error('Failed to load connection status:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchAccount = async (mailboxId: number) => {
    try {
      setSwitchingId(mailboxId);
      setConnectError(null);
      setConnectSuccess(null);
      const updated = await api.switchMailbox({ mailbox_id: mailboxId });
      setConnectionDetails(updated);
      await loadAllStatus();
      onRefreshSummary();
      if (onMailboxSwitched) onMailboxSwitched();
      setConnectSuccess(`Successfully switched active mailbox to ${updated.email_address}`);
      setTimeout(() => setConnectSuccess(null), 5000);
    } catch (err: any) {
      setConnectError('Switch failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSwitchingId(null);
    }
  };

  const handleConnectNewAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail || !newPassword) {
      setConnectError('Please provide both Gmail address and Google App Password.');
      return;
    }

    try {
      setConnecting(true);
      setConnectError(null);
      setConnectSuccess(null);

      const payload: UpdateConnectionRequest = {
        email_address: newEmail.trim(),
        app_password: newPassword.trim(),
        imap_host: imapHost.trim() || 'imap.gmail.com',
        imap_port: Number(imapPort) || 993,
        smtp_host: smtpHost.trim() || 'smtp.gmail.com',
        smtp_port: Number(smtpPort) || 587,
      };

      const res = await api.updateConnection(payload);
      setConnectionDetails(res);
      setConnectSuccess(`Successfully connected and activated ${res.email_address}! Background synchronization started.`);
      setNewEmail('');
      setNewPassword('');
      await loadAllStatus();
      onRefreshSummary();
      if (onMailboxSwitched) onMailboxSwitched();
    } catch (err: any) {
      setConnectError(err.response?.data?.detail || err.message || 'Failed to authenticate with Gmail.');
    } finally {
      setConnecting(false);
    }
  };

  const handleTestImap = async () => {
    try {
      setTestingImap(true);
      setImapResult(null);
      const res = await api.testIMAP();
      setImapResult({ success: true, ...res });
    } catch (err: any) {
      setImapResult({ success: false, message: err.response?.data?.detail || err.message });
    } finally {
      setTestingImap(false);
    }
  };

  const handleTestSmtp = async () => {
    try {
      setTestingSmtp(true);
      setSmtpResult(null);
      const res = await api.testSMTP();
      setSmtpResult({ success: true, ...res });
    } catch (err: any) {
      setSmtpResult({ success: false, message: err.response?.data?.detail || err.message });
    } finally {
      setTestingSmtp(false);
    }
  };

  const handleSyncBatch = async () => {
    try {
      setSyncing(true);
      setSyncResult(null);
      const res = await api.triggerSync(50);
      setSyncResult(res);
      await loadAllStatus();
      onRefreshSummary();
    } catch (err: any) {
      setSyncResult({ success: false, message: err.response?.data?.detail || err.message });
    } finally {
      setSyncing(false);
    }
  };

  const activeEmail = connectionDetails?.email_address || config?.gmail_address_masked || 'Not Configured';

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Global Mailbox & Gmail Connection</h2>
        <p className="text-xs text-slate-500">
          Manage connected Gmail accounts, switch active global mailbox, test IMAP/SMTP protocols, and configure credentials.
        </p>
      </div>

      {/* Global Alerts */}
      {connectSuccess && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-3 shadow-xs">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="font-semibold">{connectSuccess}</span>
        </div>
      )}

      {connectError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-3 shadow-xs">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <div>
            <p className="font-bold">Connection / Authentication Blocked</p>
            <p className="mt-0.5 text-[11px] text-rose-700">{connectError}</p>
          </div>
        </div>
      )}

      {/* Active Account Overview Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="h-14 w-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-inner">
            <Mail className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <span className="font-bold text-lg text-slate-900">
                {activeEmail}
              </span>
              {connectionDetails?.is_connected ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>ACTIVE MAILBOX</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                  <span>UNCONNECTED</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Active Data Source: Inbox, Dashboard metrics, and AutoSync are scoped strictly to this account.
            </p>
            <div className="flex items-center space-x-4 mt-2 text-xs text-slate-600 font-medium">
              <span>Emails in DB: <strong className="text-slate-900">{connectionDetails?.total_emails_stored ?? 0}</strong></span>
              <span>•</span>
              <span>IMAP: <strong className="text-slate-900">{connectionDetails?.imap_host || 'imap.gmail.com'}:{connectionDetails?.imap_port || 993}</strong></span>
              <span>•</span>
              <span>SMTP: <strong className="text-slate-900">{connectionDetails?.smtp_host || 'smtp.gmail.com'}:{connectionDetails?.smtp_port || 587}</strong></span>
            </div>
          </div>
        </div>

        <button
          onClick={handleSyncBatch}
          disabled={syncing || !connectionDetails?.is_connected}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-md transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          <span>{syncing ? 'Syncing...' : 'Sync Next 50'}</span>
        </button>
      </div>

      {/* Connected Accounts Switcher Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-slate-900">Configured Gmail Mailboxes</h3>
            <p className="text-xs text-slate-500">Switching accounts updates all inbox queries, dashboard charts, and sync workers immediately.</p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">
            {connectionDetails?.available_mailboxes?.length || 0} Account(s)
          </span>
        </div>

        <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
          {connectionDetails?.available_mailboxes && connectionDetails.available_mailboxes.length > 0 ? (
            connectionDetails.available_mailboxes.map((mb) => {
              const isActive = mb.id === connectionDetails.active_mailbox_id;
              const isSwitching = switchingId === mb.id;
              return (
                <div
                  key={mb.id}
                  className={`p-4 flex items-center justify-between transition-colors ${
                    isActive ? 'bg-indigo-50/40' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center space-x-3.5">
                    <div className={`p-2 rounded-xl ${isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                      <Mail className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-sm text-slate-800">{mb.email_address}</span>
                        {isActive && (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-700">
                            <Check className="w-3 h-3" />
                            <span>CURRENTLY ACTIVE</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center space-x-3 text-xs text-slate-500 mt-0.5">
                        <span>{mb.total_emails_stored} emails stored</span>
                        <span>•</span>
                        <span>IMAP: {mb.imap_host}:{mb.imap_port}</span>
                        <span>•</span>
                        <span>Added: {formatReceivedDateTime(mb.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    {isActive ? (
                      <span className="text-xs font-semibold text-indigo-600 px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200">
                        Active Connection
                      </span>
                    ) : (
                      <button
                        onClick={() => handleSwitchAccount(mb.id)}
                        disabled={isSwitching}
                        className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-800 text-xs font-bold transition-all disabled:opacity-50"
                      >
                        {isSwitching ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <ArrowRight className="w-3.5 h-3.5" />
                        )}
                        <span>{isSwitching ? 'Switching...' : 'Switch to this Account'}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center text-xs text-slate-500">
              No Gmail accounts configured yet. Use the form below to connect your first account.
            </div>
          )}
        </div>
      </div>

      {/* Connect New Account Form */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-6">
        <div>
          <h3 className="font-bold text-sm text-slate-900 flex items-center space-x-2">
            <Plus className="w-4 h-4 text-indigo-600" />
            <span>Connect & Switch to New Gmail Account</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Authenticate a new Gmail account. Credentials will be validated with IMAP, encrypted at rest with Fernet, and set as the active mailbox.
          </p>
        </div>

        <form onSubmit={handleConnectNewAccount} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Gmail Address <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="yourname@gmail.com"
                  required
                  className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-xs font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-hidden"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Google App Password (16 chars) <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Key className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="xxxx xxxx xxxx xxxx"
                  required
                  className="w-full pl-9 pr-10 py-2 border border-slate-300 rounded-lg text-xs font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-hidden"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* Collapsible Advanced Server Configuration */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>{showAdvanced ? 'Hide Server Settings' : 'Advanced Server Settings (IMAP & SMTP)'}</span>
            </button>

            {showAdvanced && (
              <div className="mt-3 p-4 bg-slate-50 border border-slate-200 rounded-lg grid grid-cols-2 md:grid-cols-4 gap-3 text-xs animate-in fade-in duration-150">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">IMAP Host</label>
                  <input
                    type="text"
                    value={imapHost}
                    onChange={(e) => setImapHost(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">IMAP Port</label>
                  <input
                    type="number"
                    value={imapPort}
                    onChange={(e) => setImapPort(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">SMTP Host</label>
                  <input
                    type="text"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">SMTP Port</label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded bg-white text-xs font-mono"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] text-slate-400">
              Credentials are encrypted at rest using Fernet and never logged or exposed.
            </p>
            <button
              type="submit"
              disabled={connecting}
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg text-xs font-bold shadow-md transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${connecting ? 'animate-spin' : ''}`} />
              <span>{connecting ? 'Validating with Gmail IMAP...' : 'Validate & Switch Mailbox'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Protocols Diagnostic Grid */}
      <div className="grid grid-cols-2 gap-6">
        {/* IMAP Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">Active IMAP Service</h3>
                <p className="text-xs text-slate-500">{connectionDetails?.imap_host || 'imap.gmail.com'}:{connectionDetails?.imap_port || 993} (SSL/TLS)</p>
              </div>
            </div>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
              Read-Only
            </span>
          </div>

          <div className="text-xs space-y-1.5 text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100">
            <div className="flex justify-between">
              <span>Mailbox Protocol:</span>
              <span className="font-semibold text-slate-800">IMAP4_SSL (Port 993)</span>
            </div>
            <div className="flex justify-between">
              <span>Retrieval Mode:</span>
              <span className="font-semibold text-emerald-700">BODY.PEEK[] (No \Seen alteration)</span>
            </div>
            <div className="flex justify-between">
              <span>Mailbox UIDVALIDITY:</span>
              <span className="font-semibold text-slate-800">{syncStatus?.uid_validity ?? 'Active'}</span>
            </div>
          </div>

          <button
            onClick={handleTestImap}
            disabled={testingImap}
            className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
          >
            {testingImap ? 'Testing Active IMAP Authentication...' : 'Test Active IMAP Connection'}
          </button>

          {imapResult && (
            <div className={`p-3 rounded-lg text-xs border ${imapResult.success ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
              <p className="font-bold">{imapResult.success ? 'IMAP Test Succeeded' : 'IMAP Test Failed'}</p>
              <p className="mt-0.5 text-[11px]">{imapResult.message}</p>
              {imapResult.inbox_total_messages !== undefined && (
                <p className="mt-1 font-semibold">Total INBOX Messages: {imapResult.inbox_total_messages}</p>
              )}
            </div>
          )}
        </div>

        {/* SMTP Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">Active SMTP Service</h3>
                <p className="text-xs text-slate-500">{connectionDetails?.smtp_host || 'smtp.gmail.com'}:{connectionDetails?.smtp_port || 587} (STARTTLS)</p>
              </div>
            </div>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
              Auth Only
            </span>
          </div>

          <div className="text-xs space-y-1.5 text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100">
            <div className="flex justify-between">
              <span>Transport Protocol:</span>
              <span className="font-semibold text-slate-800">SMTP + STARTTLS (Port 587)</span>
            </div>
            <div className="flex justify-between">
              <span>Automatic Sending:</span>
              <span className="font-semibold text-slate-800">Disabled (Explicit Only)</span>
            </div>
            <div className="flex justify-between">
              <span>Credential Logging:</span>
              <span className="font-semibold text-emerald-700">Strictly Redacted</span>
            </div>
          </div>

          <button
            onClick={handleTestSmtp}
            disabled={testingSmtp}
            className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
          >
            {testingSmtp ? 'Testing Active SMTP Authentication...' : 'Test Active SMTP Connection'}
          </button>

          {smtpResult && (
            <div className={`p-3 rounded-lg text-xs border ${smtpResult.success ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
              <p className="font-bold">{smtpResult.success ? 'SMTP Test Succeeded' : 'SMTP Test Failed'}</p>
              <p className="mt-0.5 text-[11px]">{smtpResult.message}</p>
            </div>
          )}
        </div>
      </div>

      {/* Sync Status Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <Database className="w-5 h-5 text-indigo-600" />
            <div>
              <h3 className="font-bold text-sm text-slate-900">Incremental Mailbox Synchronization Progress</h3>
              <p className="text-xs text-slate-500">Auto-syncing active Gmail INBOX every {syncStatus?.sync_interval_seconds || 30} seconds</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${
              syncStatus?.worker_status === 'syncing'
                ? 'bg-blue-100 text-blue-800 animate-pulse'
                : syncStatus?.worker_status === 'error'
                ? 'bg-rose-100 text-rose-800'
                : 'bg-emerald-100 text-emerald-800'
            }`}>
              Worker: {syncStatus?.worker_status || 'idle'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-slate-500 font-medium block">Total Emails in Local DB</span>
            <span className="text-lg font-bold text-slate-900">{connectionDetails?.total_emails_stored ?? 0}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-slate-500 font-medium block">Total Available in Gmail INBOX</span>
            <span className="text-lg font-bold text-slate-900">{syncStatus?.inbox_total ?? '17,570+'}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-slate-500 font-medium block">Last Processed UID</span>
            <span className="text-lg font-bold text-indigo-600">{syncStatus?.last_processed_uid || syncStatus?.highest_synced_uid || 'None'}</span>
            <span className="text-[10px] text-slate-400 block">UIDVALIDITY: {syncStatus?.uid_validity ?? 1}</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
            <span className="text-slate-500 font-medium block">Last Synchronized At</span>
            <span className="text-sm font-semibold text-slate-800">
              {formatSyncTimeAgo(syncStatus?.last_successful_sync || syncStatus?.last_synced_at)}
            </span>
            {syncStatus?.new_emails_last_sync !== undefined && (
              <span className="text-[10px] text-emerald-600 font-medium block">+{syncStatus.new_emails_last_sync} in last sync</span>
            )}
          </div>
        </div>

        {syncResult && (
          <div className={`p-3 rounded-lg text-xs border ${syncResult.success ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
            <p className="font-bold">{syncResult.success ? 'Sync Completed' : 'Sync Failed'}</p>
            <p className="mt-0.5">{syncResult.message}</p>
          </div>
        )}
      </div>
    </div>
  );
};
