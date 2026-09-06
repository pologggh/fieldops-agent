/**
 * Unified Date/Time formatting utilities strictly localized for China Standard Time (Asia/Shanghai).
 * Outputs Chinese date expressions (e.g. 2026年9月6日, 9月6日 14:00, 14:00–16:00, 周日).
 */

export const DEFAULT_TIMEZONE = 'Asia/Shanghai';

const WEEKDAYS_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

function parseDateSafe(dateStr?: string | null): Date | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Standard date-time format: 2026年9月6日 14:30
 */
export function formatDateTime(
  dateStr?: string | null,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = parseDateSafe(dateStr);
  if (!d) return '—';

  const defaultOptions: Intl.DateTimeFormatOptions = {
    timeZone: DEFAULT_TIMEZONE,
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...options,
  };

  try {
    return new Intl.DateTimeFormat('zh-CN', defaultOptions).format(d);
  } catch {
    const year = d.getFullYear();
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${year}年${month}月${day}日 ${hours}:${minutes}`;
  }
}

export const formatDateTimeZh = formatDateTime;

/**
 * Concise month-day-time format: 9月6日 14:00
 */
export function formatMonthDayTimeZh(dateStr?: string | null): string {
  const d = parseDateSafe(dateStr);
  if (!d) return '—';
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${month}月${day}日 ${hours}:${minutes}`;
}

/**
 * Time only: 14:00
 */
export function formatTimeOnly(dateStr?: string | null): string {
  const d = parseDateSafe(dateStr);
  if (!d) return '—';
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

export const formatTimeZh = formatTimeOnly;

/**
 * Date only: 2026年9月6日
 */
export function formatDateOnly(dateStr?: string | null): string {
  const d = parseDateSafe(dateStr);
  if (!d) return '—';
  const year = d.getFullYear();
  const month = d.getMonth() + 1;
  const day = d.getDate();
  return `${year}年${month}月${day}日`;
}

export const formatDateZh = formatDateOnly;

/**
 * Weekday: 周日, 周一...
 */
export function formatWeekdayZh(dateStr?: string | null): string {
  const d = parseDateSafe(dateStr);
  if (!d) return '—';
  return WEEKDAYS_ZH[d.getDay()];
}

/**
 * Time range format: 14:00–16:00 or 9月6日 14:00–16:00
 */
export function formatTimeRange(startStr?: string | null, endStr?: string | null): string {
  const start = parseDateSafe(startStr);
  const end = parseDateSafe(endStr);
  if (!start && !end) return '—';
  if (start && !end) return formatDateTime(startStr);
  if (!start && end) return formatDateTime(endStr);

  const isSameDay =
    start!.getFullYear() === end!.getFullYear() &&
    start!.getMonth() === end!.getMonth() &&
    start!.getDate() === end!.getDate();

  const startTime = formatTimeOnly(startStr);
  const endTime = formatTimeOnly(endStr);

  if (isSameDay) {
    const month = start!.getMonth() + 1;
    const day = start!.getDate();
    return `${month}月${day}日 ${startTime}–${endTime}`;
  }

  return `${formatMonthDayTimeZh(startStr)} 至 ${formatMonthDayTimeZh(endStr)}`;
}

export const formatTimeRangeZh = formatTimeRange;

/**
 * Concise window time range: 14:00–16:00
 */
export function formatTimeWindowOnly(startStr?: string | null, endStr?: string | null): string {
  const startTime = formatTimeOnly(startStr);
  const endTime = formatTimeOnly(endStr);
  if (startTime === '—' && endTime === '—') return '—';
  return `${startTime}–${endTime}`;
}

/**
 * Relative or countdown display for SLA: 剩余 42 分钟 / 已超时 15 分钟
 */
export function formatSLARemaining(deadlineStr?: string | null): { text: string; isBreached: boolean } {
  const deadline = parseDateSafe(deadlineStr);
  if (!deadline) return { text: '—', isBreached: false };

  const now = new Date();
  const diffMs = deadline.getTime() - now.getTime();
  const diffMinutes = Math.round(diffMs / (1000 * 60));

  if (diffMinutes < 0) {
    const overdueMinutes = Math.abs(diffMinutes);
    if (overdueMinutes >= 60) {
      const hours = (overdueMinutes / 60).toFixed(1);
      return { text: `已超时 ${hours} 小时`, isBreached: true };
    }
    return { text: `已超时 ${overdueMinutes} 分钟`, isBreached: true };
  }

  if (diffMinutes >= 1440) {
    const days = (diffMinutes / 1440).toFixed(1);
    return { text: `剩余 ${days} 天`, isBreached: false };
  }

  if (diffMinutes >= 60) {
    const hours = (diffMinutes / 60).toFixed(1);
    return { text: `剩余 ${hours} 小时`, isBreached: false };
  }

  return { text: `剩余 ${diffMinutes} 分钟`, isBreached: false };
}
