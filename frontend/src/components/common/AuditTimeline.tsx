import React from 'react';
import { TimelineEvent } from '../../types/api';
import { formatDateTime } from '../../utils/dateTime';
import { CheckCircle2, AlertCircle, Clock, Send, ShieldCheck, User } from 'lucide-react';

interface AuditTimelineProps {
  events: TimelineEvent[];
  className?: string;
}

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ events, className = '' }) => {
  if (!events || events.length === 0) {
    return (
      <div className="text-sm text-slate-500 py-4 italic">No audit trail events recorded.</div>
    );
  }

  const getEventIcon = (event: string) => {
    if (event.includes('created') || event.includes('intake')) {
      return <Send className="w-4 h-4 text-blue-500" />;
    }
    if (event.includes('approved') || event.includes('resolved') || event.includes('confirmed')) {
      return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    }
    if (event.includes('rejected') || event.includes('conflict') || event.includes('cancelled')) {
      return <AlertCircle className="w-4 h-4 text-rose-500" />;
    }
    if (event.includes('proposal') || event.includes('scheduled')) {
      return <Clock className="w-4 h-4 text-purple-500" />;
    }
    return <ShieldCheck className="w-4 h-4 text-slate-500" />;
  };

  return (
    <div className={`flow-root ${className}`}>
      <ul role="list" className="-mb-8">
        {events.map((evt, idx) => {
          const isLast = idx === events.length - 1;
          return (
            <li key={evt.id || idx}>
              <div className="relative pb-8">
                {!isLast && (
                  <span
                    className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-200"
                    aria-hidden="true"
                  />
                )}
                <div className="relative flex space-x-3">
                  <div>
                    <span className="h-8 w-8 rounded-full bg-white border border-slate-200 shadow-sm flex items-center justify-center ring-8 ring-white">
                      {getEventIcon(evt.event)}
                    </span>
                  </div>
                  <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{evt.summary}</p>
                      <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                        <span className="inline-flex items-center gap-1 font-medium text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                          <User className="w-3 h-3 text-slate-500" />
                          {evt.actor}
                        </span>
                        <span>•</span>
                        <span className="font-mono text-slate-500">{evt.event}</span>
                      </div>
                    </div>
                    <div className="whitespace-nowrap text-right text-xs text-slate-400">
                      <time dateTime={evt.timestamp}>{formatDateTime(evt.timestamp)}</time>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};
