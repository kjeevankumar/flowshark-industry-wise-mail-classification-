/**
 * FlowShark Precision Date & Time Utilities
 * 
 * Safely parses ISO timestamps from the server ensuring correct UTC handling
 * so the client browser displays exact local time (e.g. IST, EST, GMT)
 * and calculates relative time accurately ("Just now", "5m ago").
 */

export const parseServerDate = (val?: string | null): Date | null => {
  if (!val) return null;
  let str = String(val).trim();
  // If string lacks timezone indicator (no 'Z' and no offset like '+05:30' or '-04:00'), append 'Z'
  if (!str.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(str)) {
    str += 'Z';
  }
  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
};

/**
 * Format email received date and time for table display:
 * Shows friendly relative day + exact local time:
 * - "Today, 10:45 PM"
 * - "Yesterday, 3:12 PM"
 * - "Nov 17, 10:45 PM"
 */
export const formatReceivedDateTime = (timestamp?: string | null): string => {
  const date = parseServerDate(timestamp);
  if (!date) return 'N/A';

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  const timeStr = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });

  if (isToday) {
    return `Today, ${timeStr}`;
  }
  if (isYesterday) {
    return `Yesterday, ${timeStr}`;
  }

  const isCurrentYear = date.getFullYear() === now.getFullYear();
  const monthDay = date.toLocaleDateString([], { month: 'short', day: 'numeric' });

  if (isCurrentYear) {
    return `${monthDay}, ${timeStr}`;
  }
  return `${monthDay} ${date.getFullYear()}, ${timeStr}`;
};

/**
 * Format relative sync time for header & status indicators:
 * - "Just now" (0-15s)
 * - "30s ago"
 * - "5m ago"
 * - "2h ago"
 * - Or exact local time if older
 */
export const formatSyncTimeAgo = (timestamp?: string | null): string => {
  const date = parseServerDate(timestamp);
  if (!date) return 'Never';

  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSec < 15) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
};
