import React, { useEffect, useRef, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { InboxPage } from './pages/InboxPage';
import { ConnectionPage } from './pages/ConnectionPage';
import { SettingsPage } from './pages/SettingsPage';
import { EmailDetailModal } from './components/EmailDetailModal';
import { ConnectionDetailsResponse, DashboardSummary, Email, SyncStatus } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'inbox' | 'connection' | 'settings'>('dashboard');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [connectionDetails, setConnectionDetails] = useState<ConnectionDetailsResponse | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);

  const prevTotalRef = useRef<number>(-1);
  const prevSyncTimeRef = useRef<string | undefined>(undefined);

  // Initial load
  useEffect(() => {
    loadSummary();
    loadSyncStatus();
    loadConnectionDetails();
  }, []);

  // Periodic polling every 10 seconds for real-time synchronization updates
  useEffect(() => {
    const pollInterval = setInterval(() => {
      loadSyncStatus();
    }, 10000);

    return () => clearInterval(pollInterval);
  }, []);

  const loadSummary = async () => {
    try {
      const data = await api.getDashboardSummary();
      setSummary(data);
    } catch (err) {
      console.error('Failed to load dashboard summary:', err);
    }
  };

  const loadConnectionDetails = async () => {
    try {
      const conn = await api.getConnectionDetails();
      setConnectionDetails(conn);
    } catch (err) {
      console.error('Failed to load connection details:', err);
    }
  };

  const loadSyncStatus = async () => {
    try {
      const statusData = await api.getSyncStatus();
      setSyncStatus(statusData);

      // Check if new emails were ingested or sync completed
      const totalStored = statusData.total_emails_stored ?? statusData.total_synced_in_db;
      const lastSync = statusData.last_successful_sync ?? statusData.last_synced_at;

      if (prevTotalRef.current !== -1 && totalStored > prevTotalRef.current) {
        console.log(`Detected new emails (${totalStored - prevTotalRef.current} new). Refreshing views.`);
        loadSummary();
        loadConnectionDetails();
        setRefreshTrigger((prev) => prev + 1);
      } else if (prevSyncTimeRef.current && lastSync && lastSync !== prevSyncTimeRef.current) {
        loadSummary();
        loadConnectionDetails();
        setRefreshTrigger((prev) => prev + 1);
      }

      prevTotalRef.current = totalStored;
      prevSyncTimeRef.current = lastSync;
    } catch (err) {
      console.error('Failed to poll sync status:', err);
    }
  };

  const handleSwitchMailbox = async (mailboxId: number) => {
    try {
      const updated = await api.switchMailbox({ mailbox_id: mailboxId });
      setConnectionDetails(updated);
      setSelectedEmail(null);
      await Promise.all([loadSummary(), loadSyncStatus(), loadConnectionDetails()]);
      setRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      console.error('Failed to switch mailbox:', err);
      throw err;
    }
  };

  const handleNavigate = (tab: string, category?: string) => {
    setCurrentTab(tab as any);
    setCategoryFilter(category);
  };

  const getPageTitle = () => {
    if (currentTab === 'dashboard') return 'Lead Intelligence Dashboard';
    if (currentTab === 'connection') return 'Gmail Connection Management';
    if (currentTab === 'settings') return 'AI Engine & System Settings';
    if (categoryFilter) {
      return categoryFilter.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase());
    }
    return 'All Ingested Communications';
  };

  const getPageSubtitle = () => {
    if (currentTab === 'dashboard') return 'Real-time pipeline metrics and conversation classification';
    if (currentTab === 'connection') return 'Monitor IMAP read-only, background sync worker, and SMTP states';
    if (currentTab === 'settings') return 'Provider keys, confidence thresholds, and benchmark evals';
    return 'Browse, search, and batch-classify synchronized emails';
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        categoryFilter={categoryFilter}
        onNavigate={handleNavigate}
        summary={summary}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        <Header
          title={getPageTitle()}
          subtitle={getPageSubtitle()}
          summary={summary}
          syncStatus={syncStatus}
          connectionDetails={connectionDetails}
          onRefresh={() => {
            loadSummary();
            loadSyncStatus();
            loadConnectionDetails();
            setRefreshTrigger((prev) => prev + 1);
          }}
          onSwitchMailbox={handleSwitchMailbox}
          onNavigateToConnection={() => setCurrentTab('connection')}
        />

        <main className="flex-1 overflow-y-auto">
          {currentTab === 'dashboard' && (
            <DashboardPage
              summary={summary}
              onNavigate={handleNavigate}
              onSelectEmail={(em) => setSelectedEmail(em)}
              onRefresh={() => {
                loadSummary();
                loadSyncStatus();
                loadConnectionDetails();
              }}
            />
          )}

          {currentTab === 'inbox' && (
            <InboxPage
              key={`${connectionDetails?.active_mailbox_id ?? 0}-${categoryFilter || 'all'}`}
              categoryFilter={categoryFilter}
              refreshTrigger={refreshTrigger}
              onSelectEmail={(em) => setSelectedEmail(em)}
              onRefreshSummary={() => {
                loadSummary();
                loadConnectionDetails();
              }}
            />
          )}

          {currentTab === 'connection' && (
            <ConnectionPage
              onRefreshSummary={() => {
                loadSummary();
                loadConnectionDetails();
              }}
              onMailboxSwitched={() => {
                loadSummary();
                loadSyncStatus();
                loadConnectionDetails();
                setRefreshTrigger((prev) => prev + 1);
              }}
            />
          )}

          {currentTab === 'settings' && (
            <SettingsPage />
          )}
        </main>
      </div>

      {/* Email Detail Drawer / Modal - Keyed by ID for absolute lifecycle isolation */}
      {selectedEmail && (
        <EmailDetailModal
          key={selectedEmail.id}
          email={selectedEmail}
          onClose={() => setSelectedEmail(null)}
          onUpdated={() => {
            loadSummary();
            api.getEmailDetail(selectedEmail.id).then(setSelectedEmail).catch(() => {});
          }}
        />
      )}
    </div>
  );
};

export default App;
