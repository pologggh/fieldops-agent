import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import * as customerApi from '../../api/customerApi';
import {
  ConversationView,
  ConversationSummaryItem,
  ConversationDraft,
} from '../../types/customer';
import {
  Sparkles,
  Send,
  Bot,
  User,
  CheckCircle2,
  AlertTriangle,
  Clock,
  MapPin,
  Wrench,
  Plus,
  XCircle,
  ArrowRight,
  RefreshCw,
  FileText,
  ShieldAlert,
  Loader2,
  History,
  Zap,
  Droplets,
  Calendar,
  Check,
  ChevronRight,
  Mic,
  MicOff,
  Volume2,
} from 'lucide-react';
import { Dialog, Button, Drawer } from '../../components/ui';
import { formatTimeZh, formatDateZh, formatDateTimeZh } from '../../utils/dateTime';
import {
  t,
  getCustomerStatusText,
  getServiceTypeText,
  getUrgencyText,
  getMissingFieldText,
} from '../../locales';

export const CustomerAssistantPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeConvIdParam = searchParams.get('id');
  const promptParam = searchParams.get('prompt');

  const [conversation, setConversation] = useState<ConversationView | null>(null);
  const [conversationsList, setConversationsList] = useState<ConversationSummaryItem[]>([]);
  const [inputText, setInputText] = useState(promptParam || '');
  const [isSending, setIsSending] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isLoadingConv, setIsLoadingConv] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastFailedText, setLastFailedText] = useState<string | null>(null);

  // Cancellation modal state
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // History drawer state (replaces the permanent desktop right-column clutter)
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);

  // Mobile drawer state for draft summary
  const [showMobileDraftSheet, setShowMobileDraftSheet] = useState(false);

  // Speech-to-Text state
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
    };
  }, []);

  const toggleSpeechRecognition = () => {
    setSpeechError(null);
    const SpeechRecognitionClass =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionClass) {
      setSpeechError('您的浏览器环境尚未支持 Web Speech 语音接口，建议使用 Chrome/Edge 浏览器或直接键入文字。');
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognitionClass();
      recognition.lang = 'zh-CN';
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
        setSpeechError(null);
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript.trim()) {
          setInputText((prev) => (prev ? `${prev} ${transcript.trim()}` : transcript.trim()));
        }
      };

      recognition.onerror = (event: any) => {
        if (event.error === 'not-allowed') {
          setSpeechError('麦克风权限被拒绝，请在浏览器地址栏允许麦克风权限后重试。');
        } else if (event.error !== 'no-speech') {
          setSpeechError(`语音识别提示：${event.error || '未识别到清晰语音'}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      setSpeechError('启动语音识别失败，请检查浏览器权限配置。');
      setIsListening(false);
    }
  };

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    loadConversationListAndActive();
  }, [activeConvIdParam]);

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages, isSending]);

  const loadConversationListAndActive = async () => {
    setIsLoadingConv(true);
    setErrorMsg(null);
    try {
      const list = await customerApi.fetchConversations();
      setConversationsList(list);

      let targetId: number | null = null;
      if (activeConvIdParam) {
        targetId = parseInt(activeConvIdParam, 10);
      } else if (list.length > 0) {
        const active = list.find((c) => c.status === 'active' || c.status === 'awaiting_confirmation');
        targetId = active ? active.id : list[0].id;
      }

      if (targetId) {
        const conv = await customerApi.fetchConversation(targetId);
        setConversation(conv);
      } else {
        const newConv = await customerApi.createConversation();
        setConversation(newConv);
        setSearchParams({ id: newConv.id.toString() });
        setConversationsList([
          {
            id: newConv.id,
            status: newConv.status,
            service_type: newConv.draft.service_type,
            draft_preview: '新建对话',
            created_at: newConv.created_at,
            updated_at: newConv.updated_at,
          },
        ]);
      }
    } catch (err: any) {
      setErrorMsg(err.message || '加载对话会话失败，请刷新重试。');
    } finally {
      setIsLoadingConv(false);
    }
  };

  const handleStartNew = async () => {
    setIsLoadingConv(true);
    setErrorMsg(null);
    try {
      const newConv = await customerApi.createConversation();
      setConversation(newConv);
      setSearchParams({ id: newConv.id.toString() });
      const list = await customerApi.fetchConversations();
      setConversationsList(list);
    } catch (err: any) {
      setErrorMsg(err.message || '初始化新对话失败，请重试。');
    } finally {
      setIsLoadingConv(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const messageContent = (textToSend || inputText).trim();
    if (!conversation || !messageContent || isSending) return;

    setInputText('');
    setIsSending(true);
    setErrorMsg(null);
    setLastFailedText(null);

    const clientMessageId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}`;

    try {
      const updated = await customerApi.sendConversationMessage(conversation.id, {
        content: messageContent,
        client_message_id: clientMessageId,
      });
      setConversation(updated);
      customerApi.fetchConversations().then(setConversationsList).catch(() => {});
    } catch (err: any) {
      setErrorMsg(err.message || '暂时无法处理该消息，请重试。');
      setLastFailedText(messageContent);
    } finally {
      setIsSending(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage();
  };

  const handleRetryLastMessage = () => {
    if (lastFailedText) {
      setInputText(lastFailedText);
      setLastFailedText(null);
      setErrorMsg(null);
    }
  };

  const handleConfirmAndSubmit = async () => {
    if (!conversation || conversation.status !== 'awaiting_confirmation' || isConfirming) return;

    setIsConfirming(true);
    setErrorMsg(null);
    try {
      const idempotencyKey = `confirm-${conversation.id}-${conversation.draft_version}`;
      await customerApi.confirmConversation(conversation.id, idempotencyKey);
      const updated = await customerApi.fetchConversation(conversation.id);
      setConversation(updated);
      customerApi.fetchConversations().then(setConversationsList).catch(() => {});
      setShowMobileDraftSheet(false);
    } catch (err: any) {
      setErrorMsg(err.message || '提交服务请求失败，请重试。');
    } finally {
      setIsConfirming(false);
    }
  };

  const confirmCancelConversation = async () => {
    if (!conversation || conversation.status === 'submitted') return;
    setIsCancelling(true);
    try {
      const updated = await customerApi.cancelConversation(conversation.id);
      setConversation(updated);
      customerApi.fetchConversations().then(setConversationsList).catch(() => {});
      setShowCancelDialog(false);
    } catch (err: any) {
      setErrorMsg(err.message || '取消对话失败，请重试。');
    } finally {
      setIsCancelling(false);
    }
  };

  const draft: ConversationDraft | undefined = conversation?.draft;
  const isSubmitted = conversation?.status === 'submitted';
  const isAwaitingConfirm = conversation?.status === 'awaiting_confirmation';
  const isCancelled = conversation?.status === 'cancelled';

  // Completion calculation: 5 key fields
  const completionStats = useMemo(() => {
    const total = 5;
    let completed = 0;
    if (draft?.service_type && draft.service_type !== 'Other') completed++;
    if (draft?.problem_description && draft.problem_description.trim().length > 0) completed++;
    if (draft?.location && !draft.missing_fields?.includes('location')) completed++;
    if (draft?.preferred_time && !draft.missing_fields?.includes('preferred_time')) completed++;
    if (draft?.urgency) completed++;
    const percent = Math.min(100, Math.round((completed / total) * 100));
    return { completed, total, percent };
  }, [draft]);

  // Stepper state
  const currentStep = isSubmitted ? 3 : isAwaitingConfirm ? 3 : completionStats.completed >= 2 ? 2 : 1;

  // Render assistant message content with Chinese localization
  const formatAssistantMessageContent = (content: string, metadata?: any) => {
    if (
      metadata?.action === 'greeting' ||
      content.includes('Hello! I am your FieldOps customer service assistant') ||
      content.includes('FieldOps customer service assistant')
    ) {
      return t.conversation.welcomeMessage;
    }
    if (content.includes('Which district, address, or building is the property located in?')) {
      return '收到您的故障描述！请问您的具体服务地址（所在区域、街道或小区门牌号）在哪里？';
    }
    if (content.includes('What date and time window would you prefer a technician to visit?')) {
      const match = content.match(/located in (.*?)\./);
      const loc = match ? match[1] : '';
      return `好的，服务地址已确认为${loc ? `【${loc}】` : ''}。请问您希望工程师在什么时间段上门服务？（例如：明天下午 14:00-17:00、周末上午等）`;
    }
    if (content.includes('Could you please describe what issue or malfunction you are experiencing?')) {
      return '请详细描述您遇到的设备问题或故障现象，以便我们为您匹配最专业的工程师。';
    }
    if (content.includes('I have summarized your service request:')) {
      return content
        .replace('I have summarized your service request:', '为您汇总的服务预约需求如下：')
        .replace('- Trade:', '• 服务品类：')
        .replace('- Issue:', '• 故障描述：')
        .replace('- Location:', '• 服务地址：')
        .replace('- Preferred Visit:', '• 期望上门时间：')
        .replace(
          "Please review the details above. When you are ready, click 'Confirm & Submit' to send this request to our dispatch team.",
          '请核对以上信息。确认无误后，点击右侧“确认并提交需求”按钮，我们将立即为您智能派发工程师。'
        );
    }
    return content;
  };

  // Quick Prompt Cards for welcome state (5 exact requested categories)
  const promptCards = [
    {
      icon: Wrench,
      title: '空调不制冷',
      desc: '吹出常温风、制冷效果减弱或伴随异味异响',
      prompt: '办公室空调不制冷，一直在吹常温风，需要师傅上门检修。',
      color: 'from-indigo-500/10 to-violet-500/10 text-indigo-600',
    },
    {
      icon: Droplets,
      title: '厨房漏水',
      desc: '水管破裂、水压异常或接头处持续渗水',
      prompt: '厨房水龙头管道处在漏水，地面有明显积水，需要尽快处理。',
      color: 'from-sky-500/10 to-blue-500/10 text-sky-600',
    },
    {
      icon: Zap,
      title: '电路频繁跳闸',
      desc: '总电闸跳闸、插座无电或电路发热异常',
      prompt: '室内配电箱空气开关频繁跳闸，合闸后依然跳开，插座没电。',
      color: 'from-amber-500/10 to-orange-500/10 text-amber-600',
    },
    {
      icon: RefreshCw,
      title: '网络突然断开',
      desc: '路由器红灯常亮、WiFi 掉线或网速异常',
      prompt: '宽带网络突然断开了，路由器红灯常亮无法上网。',
      color: 'from-purple-500/10 to-pink-500/10 text-purple-600',
    },
    {
      icon: Calendar,
      title: '想预约明天下午维修',
      desc: '指定明天下午 14:00–16:00 工程师上门排期',
      prompt: '想预约明天下午 14:00 至 16:00 之间安排工程师上门检修设备。',
      color: 'from-emerald-500/10 to-teal-500/10 text-emerald-600',
    },
  ];

  // Render Intelligence / Draft Panel Content with Progressive Disclosure
  const renderIntelligencePanel = () => {
    if (completionStats.completed === 0 && !isSubmitted && !isCancelled) {
      return (
        <div className="space-y-4">
          <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                  服务需求解析
                </h3>
                <p className="text-[11px] text-slate-400">
                  {t.conversation.draft.title}
                </p>
              </div>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600">
              正在了解需求
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 text-slate-700 text-xs space-y-3">
            <div className="font-bold text-slate-900 flex items-center gap-1.5 text-sm">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <span>正在了解您的需求</span>
            </div>
            <p className="text-slate-600 leading-relaxed">
              请在左侧对话框告诉我们遇到的故障现象、设备型号或地点，AI 助手将自动帮您识别工种、评估紧急度并梳理报修要素。
            </p>
            <div className="pt-2 border-t border-indigo-100/60 text-[11px] text-slate-500 space-y-1">
              <p>💡 您可以提供：故障现象、发生位置、期望到达时间段等。</p>
            </div>
          </div>
        </div>
      );
    }

    const isHighPriority = draft?.urgency === 'emergency' || draft?.urgency === 'high';

    return (
      <div className="space-y-4">
        {/* Panel Header & Meter */}
        <div className="pb-3.5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                  服务需求解析
                </h3>
                <p className="text-[11px] text-slate-400">
                  {t.conversation.draft.title}
                </p>
              </div>
            </div>

            <span
              className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                isSubmitted
                  ? 'bg-sky-50 text-sky-700 border border-sky-200'
                  : isAwaitingConfirm || completionStats.percent === 100
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : isCancelled
                  ? 'bg-slate-100 text-slate-600'
                  : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
              }`}
            >
              {isSubmitted
                ? t.conversation.draft.statusSubmitted
                : isAwaitingConfirm || completionStats.percent === 100
                ? '报修信息已整理完成'
                : isCancelled
                ? t.conversation.draft.statusCancelled
                : `已整理 ${completionStats.completed} / ${completionStats.total} 项信息`}
            </span>
          </div>

          {/* Completion Progress Bar */}
          {!isSubmitted && !isCancelled && (
            <div className="mt-3.5 pt-3 border-t border-slate-100/80">
              <div className="flex items-center justify-between text-xs mb-1.5 font-medium">
                <span className="text-slate-500">
                  已识别 <strong className="text-slate-900 font-bold">{completionStats.completed}</strong> / {completionStats.total} 项信息
                </span>
                <span className="text-indigo-600 font-mono font-bold">{completionStats.percent}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 rounded-full ${
                    completionStats.percent === 100
                      ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
                      : 'bg-gradient-to-r from-indigo-500 to-violet-500'
                  }`}
                  style={{ width: `${completionStats.percent}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* High Priority Banner if applicable */}
        {isHighPriority && !isSubmitted && !isCancelled && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2 font-medium">
            <Zap className="w-4 h-4 text-rose-600 shrink-0" />
            <span>需要优先处理：已识别紧急报修信号，将开通快速排班通道！</span>
          </div>
        )}

        {/* Safety Warning Banner if any */}
        {draft?.safety_warning && (
          <div className="p-3.5 rounded-xl bg-amber-50/90 border border-amber-200 text-amber-900 text-xs flex items-start space-x-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="leading-relaxed font-medium">{draft.safety_warning}</div>
          </div>
        )}

      {/* Live Extracted Fields List */}
      <div className="space-y-2 text-xs">
        {/* Service Trade */}
        <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-100 flex items-center justify-between hover:bg-slate-100/60 transition-colors">
          <div className="flex items-center space-x-2.5 text-slate-600">
            <div className="w-6 h-6 rounded-md bg-white text-indigo-600 flex items-center justify-center shadow-2xs border border-slate-100">
              <Wrench className="w-3.5 h-3.5" />
            </div>
            <span className="font-medium text-slate-700">{t.conversation.draft.specialtyTrade}</span>
          </div>
          <span className="font-bold text-slate-900 text-right">
            {getServiceTypeText(draft?.service_type)}
          </span>
        </div>

        {/* Urgency */}
        <div className="p-3 rounded-xl bg-slate-50/80 border border-slate-100 flex items-center justify-between hover:bg-slate-100/60 transition-colors">
          <div className="flex items-center space-x-2.5 text-slate-600">
            <div className="w-6 h-6 rounded-md bg-white text-amber-600 flex items-center justify-center shadow-2xs border border-slate-100">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
            <span className="font-medium text-slate-700">{t.conversation.draft.assessedUrgency}</span>
          </div>
          <span
            className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
              draft?.urgency === 'emergency'
                ? 'bg-rose-100 text-rose-800'
                : draft?.urgency === 'high'
                ? 'bg-amber-100 text-amber-800'
                : 'bg-slate-200 text-slate-800'
            }`}
          >
            {getUrgencyText(draft?.urgency)}
          </span>
        </div>

        {/* Location */}
        <div className={`p-3 rounded-xl border flex items-center justify-between transition-colors ${
          draft?.location
            ? 'bg-slate-50/80 border-slate-100'
            : 'bg-amber-50/50 border-amber-200/80'
        }`}>
          <div className="flex items-center space-x-2.5 text-slate-600">
            <div className="w-6 h-6 rounded-md bg-white text-slate-500 flex items-center justify-center shadow-2xs border border-slate-100">
              <MapPin className="w-3.5 h-3.5 text-indigo-600" />
            </div>
            <span className="font-medium text-slate-700">{t.conversation.draft.location}</span>
          </div>
          <span
            className={`font-semibold text-right max-w-[60%] truncate ${
              draft?.location ? 'text-slate-900' : 'text-amber-700'
            }`}
          >
            {draft?.location ? `✓ ${draft.location}` : t.conversation.draft.needed}
          </span>
        </div>

        {/* Preferred Time */}
        <div className={`p-3 rounded-xl border flex items-center justify-between transition-colors ${
          draft?.preferred_time
            ? 'bg-slate-50/80 border-slate-100'
            : 'bg-amber-50/50 border-amber-200/80'
        }`}>
          <div className="flex items-center space-x-2.5 text-slate-600">
            <div className="w-6 h-6 rounded-md bg-white text-slate-500 flex items-center justify-center shadow-2xs border border-slate-100">
              <Clock className="w-3.5 h-3.5 text-indigo-600" />
            </div>
            <span className="font-medium text-slate-700">{t.conversation.draft.preferredVisit}</span>
          </div>
          <span
            className={`font-semibold text-right max-w-[60%] truncate ${
              draft?.preferred_time ? 'text-slate-900' : 'text-amber-700'
            }`}
          >
            {draft?.preferred_time ? `✓ ${draft.preferred_time}` : t.conversation.draft.needed}
          </span>
        </div>

        {/* Problem Description Summary Box */}
        <div className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-100 space-y-1.5">
          <div className="flex items-center space-x-2 text-slate-700 font-medium">
            <FileText className="w-3.5 h-3.5 text-slate-400" />
            <span>{t.conversation.draft.problemSummary}</span>
          </div>
          <p
            className={`text-xs leading-relaxed ${
              draft?.problem_description ? 'text-slate-800' : 'text-slate-400 italic'
            }`}
          >
            {draft?.problem_description || t.conversation.draft.problemPlaceholder}
          </p>
        </div>
      </div>

      {/* Missing Information Checklist */}
      {draft && draft.missing_fields && draft.missing_fields.length > 0 && !isSubmitted && !isCancelled && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200/80 space-y-1.5">
          <div className="flex items-center space-x-1.5 text-amber-900 font-bold text-xs">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>{t.conversation.draft.stillNeeded}</span>
          </div>
          <ul className="text-xs text-amber-800 space-y-1 ml-5 list-disc">
            {draft.missing_fields.map((field) => (
              <li key={field}>
                {getMissingFieldText(field)}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-amber-700/90 pt-1">
            {t.conversation.draft.tip}
          </p>
        </div>
      )}

      {/* Submission / Confirmation Area */}
      {isSubmitted ? (
        <div className="pt-2 space-y-2.5">
          <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 text-sky-900 text-xs space-y-2 text-center">
            <CheckCircle2 className="w-6 h-6 text-sky-600 mx-auto" />
            <p className="font-bold text-sm">{t.conversation.draft.submittedTitle}</p>
            <p className="text-slate-600 text-xs leading-relaxed">
              {t.conversation.draft.submittedDesc}
            </p>
            {conversation.submitted_service_request_id && (
              <button
                type="button"
                onClick={() =>
                  navigate(`/customer/requests/${conversation.submitted_service_request_id}`)
                }
                className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-xs transition-colors cursor-pointer"
              >
                {t.conversation.draft.viewRequest} #{conversation.submitted_service_request_id}
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={handleStartNew}
            className="w-full py-2.5 px-4 rounded-xl border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold text-xs transition-colors cursor-pointer"
          >
            {t.conversation.draft.startAnother}
          </button>
        </div>
      ) : isAwaitingConfirm ? (
        <div className="pt-2 space-y-2">
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-600 shrink-0 font-bold" />
            <span className="font-semibold">需求信息已完整，可确认并提交工单</span>
          </div>

          <button
            type="button"
            onClick={handleConfirmAndSubmit}
            disabled={isConfirming}
            className="w-full inline-flex items-center justify-center py-3.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-bold text-xs shadow-md hover:shadow-lg transition-all disabled:opacity-50 cursor-pointer"
          >
            {isConfirming ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {t.conversation.draft.submitting}
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-1.5 text-indigo-200" />
                {t.conversation.draft.confirmAndSubmit}
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </>
            )}
          </button>
          <p className="text-[11px] text-center text-slate-400">
            {t.conversation.draft.submitNotice}
          </p>
        </div>
      ) : (
        <div className="pt-2">
          <button
            type="button"
            disabled
            className="w-full py-2.5 px-4 rounded-xl bg-slate-100 text-slate-400 font-semibold text-xs border border-slate-200 cursor-not-allowed text-center"
          >
            {t.conversation.draft.provideDetailsHint}
          </button>
        </div>
      )}
    </div>
  );
};

  return (
    <div className="space-y-4 max-w-[1440px] mx-auto pb-12">
      {/* Top Presence & Assistant Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-slate-900 via-indigo-950 to-indigo-900 text-white flex items-center justify-center shadow-xs ring-1 ring-slate-900/10">
            <Bot className="w-5 h-5 text-indigo-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                {t.conversation.headerTitle}
              </h1>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/80">
                <Sparkles className="w-3 h-3 text-indigo-600" />
                {t.conversation.assistantBadge}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {t.conversation.headerSubtitle}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2 self-start sm:self-auto">
          {conversationsList.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowHistoryDrawer(true)}
              leftIcon={<History className="w-3.5 h-3.5 text-slate-500" />}
            >
              <span>{t.conversation.buttons.recentConversations}</span>
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] text-slate-600 font-mono">
                {conversationsList.length}
              </span>
            </Button>
          )}

          {conversation && !isSubmitted && !isCancelled && (
            <button
              type="button"
              onClick={() => setShowCancelDialog(true)}
              className="inline-flex items-center px-3 py-1.5 rounded-xl border border-slate-200 hover:border-rose-200 bg-white hover:bg-rose-50 text-slate-500 hover:text-rose-700 text-xs font-semibold transition-colors cursor-pointer"
            >
              <XCircle className="w-3.5 h-3.5 mr-1 text-slate-400 group-hover:text-rose-600" />
              {t.conversation.buttons.cancelConversation}
            </button>
          )}

          <Button
            variant="primary"
            size="sm"
            onClick={handleStartNew}
            disabled={isLoadingConv}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
            className="bg-indigo-600 hover:bg-indigo-700"
          >
            {t.conversation.buttons.newConversation}
          </Button>
        </div>
      </div>

      {/* Lightweight Stepper Breadcrumb */}
      <div className="px-4 py-2.5 surface-card rounded-xl flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
              currentStep >= 1 ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-400'
            }`}
          >
            1
          </span>
          <span className={currentStep >= 1 ? 'text-slate-900 font-bold' : 'text-slate-400'}>
            {t.conversation.steps.step1}
          </span>
        </div>

        <div className="flex-1 max-w-[80px] sm:max-w-[120px] h-0.5 bg-slate-200 mx-2" />

        <div className="flex items-center gap-2">
          <span
            className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
              currentStep >= 2 ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-400'
            }`}
          >
            2
          </span>
          <span className={currentStep >= 2 ? 'text-slate-900 font-bold' : 'text-slate-400'}>
            {t.conversation.steps.step2}
          </span>
        </div>

        <div className="flex-1 max-w-[80px] sm:max-w-[120px] h-0.5 bg-slate-200 mx-2" />

        <div className="flex items-center gap-2">
          <span
            className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
              currentStep >= 3 ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-400'
            }`}
          >
            3
          </span>
          <span className={currentStep >= 3 ? 'text-emerald-700 font-bold' : 'text-slate-400'}>
            {t.conversation.steps.step3}
          </span>
        </div>
      </div>

      {/* Mobile Sticky Draft Quick-Toggle Bar */}
      <div className="lg:hidden p-3 bg-indigo-50/90 border border-indigo-200 rounded-xl flex items-center justify-between text-xs shadow-2xs">
        <div className="flex items-center gap-2 truncate mr-2">
          <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
          <span className="font-semibold text-indigo-950 truncate">
            {t.conversation.draft.title}：{getServiceTypeText(draft?.service_type)}
          </span>
          <span className="text-[11px] text-indigo-700 font-medium shrink-0">
            • {completionStats.percent}%
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowMobileDraftSheet(true)}
          className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg font-bold text-xs shrink-0 shadow-xs cursor-pointer"
        >
          {t.conversation.buttons.viewDraft}
        </button>
      </div>

      {/* Main Grid: Desktop ~68% Conversation Canvas + ~32% Intelligence Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Chat Pane */}
        <div className="lg:col-span-8 flex flex-col surface-elevated rounded-2xl h-[700px] overflow-hidden">
          {/* Messages Canvas */}
          <div className="flex-1 min-h-0 p-4 sm:p-6 overflow-y-auto space-y-4 bg-slate-50/40">
            {isLoadingConv ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-2">
                <Loader2 className="w-7 h-7 animate-spin text-indigo-600" />
                <span className="text-xs font-medium">{t.conversation.input.connecting}</span>
              </div>
            ) : !conversation ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <p className="text-xs">{t.conversation.input.noActiveConv}</p>
              </div>
            ) : (
              <>
                {/* Welcome Message / Prompt Hub */}
                {conversation.messages.length <= 1 && (
                  <div className="space-y-4 py-2">
                    <div className="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-2xs space-y-2">
                      <div className="flex items-center gap-2 text-indigo-600 text-xs font-bold">
                        <Sparkles className="w-4 h-4" />
                        <span>FieldOps 智能需求助手</span>
                      </div>
                      <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
                        {t.conversation.welcomeMessage}
                      </p>
                    </div>

                    {/* 2x2 Quick Prompt Cards */}
                    <div>
                      <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2.5 px-0.5">
                        您可以这样描述问题：
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        {promptCards.map((card) => {
                          const CardIcon = card.icon;
                          return (
                            <button
                              key={card.title}
                              type="button"
                              onClick={() => handleSendMessage(card.prompt)}
                              disabled={isSending || isLoadingConv}
                              className="p-3.5 rounded-xl bg-white border border-slate-200/80 hover:border-indigo-300 hover:shadow-card text-left transition-all group cursor-pointer disabled:opacity-50"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex items-center space-x-2.5">
                                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-tr ${card.color} flex items-center justify-center shrink-0`}>
                                    <CardIcon className="w-4 h-4" />
                                  </div>
                                  <div>
                                    <div className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                                      {card.title}
                                    </div>
                                    <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                                      {card.desc}
                                    </div>
                                  </div>
                                </div>
                                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all mt-1" />
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {/* Conversation Messages */}
                {conversation.messages.map((msg) => {
                  if (msg.role === 'customer') {
                    return (
                      <div key={msg.id} className="flex justify-end items-end space-x-2 pt-1">
                        <div className="max-w-[75%] rounded-2xl rounded-br-xs px-4 py-2.5 bg-indigo-600 text-white text-xs shadow-xs leading-relaxed">
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                          <span className="block text-[10px] text-indigo-200 text-right mt-1 font-mono opacity-80">
                            {formatTimeZh(msg.created_at)}
                          </span>
                        </div>
                        <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs shrink-0 mb-0.5">
                          <User className="w-3.5 h-3.5" />
                        </div>
                      </div>
                    );
                  }

                  if (msg.role === 'system_event') {
                    return (
                      <div key={msg.id} className="flex justify-center my-2">
                        <div className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-sky-50 border border-sky-200 text-sky-700 text-xs font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5 text-sky-600" />
                          <span>{msg.content}</span>
                        </div>
                      </div>
                    );
                  }

                  // Assistant Response Block
                  return (
                    <div key={msg.id} className="flex items-start space-x-3 pt-1">
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-slate-900 to-indigo-950 flex items-center justify-center text-white shrink-0 shadow-xs ring-1 ring-slate-900/10 mt-0.5">
                        <Bot className="w-4 h-4 text-indigo-300" />
                      </div>
                      <div className="max-w-[85%] rounded-2xl rounded-tl-xs px-4 py-3.5 bg-white border border-slate-200/90 text-slate-800 text-xs shadow-xs leading-relaxed space-y-2.5">
                        <div className="flex items-center justify-between pb-1 border-b border-slate-100">
                          <span className="font-bold text-slate-900 flex items-center gap-1.5">
                            <Sparkles className="w-3 h-3 text-indigo-600" />
                            FieldOps 智能助手
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {formatTimeZh(msg.created_at)}
                          </span>
                        </div>

                        <p className="whitespace-pre-wrap text-slate-700 text-xs sm:text-[13px] leading-relaxed">
                          {formatAssistantMessageContent(msg.content, msg.metadata)}
                        </p>

                        {/* Inline recognized entity chips */}
                        {draft && (draft.service_type || draft.location || draft.preferred_time) && (
                          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5">
                            <span className="text-[10px] text-slate-400 font-medium">已识别：</span>
                            {draft.service_type && draft.service_type !== 'Other' && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 text-[10px] font-semibold">
                                <Wrench className="w-2.5 h-2.5 mr-1" />
                                {getServiceTypeText(draft.service_type)}
                              </span>
                            )}
                            {draft.location && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 text-[10px] font-semibold">
                                <MapPin className="w-2.5 h-2.5 mr-1" />
                                {draft.location}
                              </span>
                            )}
                            {draft.preferred_time && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-sky-50 text-sky-700 text-[10px] font-semibold">
                                <Clock className="w-2.5 h-2.5 mr-1" />
                                {draft.preferred_time}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* In-Flight Processing Indicator */}
                {isSending && (
                  <div className="flex items-start space-x-3 pt-1">
                    <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white shrink-0 animate-pulse">
                      <Bot className="w-4 h-4 text-indigo-300" />
                    </div>
                    <div className="rounded-2xl rounded-tl-xs px-4 py-2.5 bg-white border border-slate-200 text-slate-600 text-xs shadow-xs flex items-center space-x-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                      <span className="font-medium">{t.conversation.input.reviewing}</span>
                    </div>
                  </div>
                )}

                {/* Error & Retry Banner */}
                {errorMsg && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
                      <span>{errorMsg}</span>
                    </div>
                    {lastFailedText && (
                      <button
                        type="button"
                        onClick={handleRetryLastMessage}
                        className="inline-flex items-center px-2.5 py-1 rounded-md bg-white border border-rose-300 text-rose-800 font-semibold hover:bg-rose-100 transition-colors cursor-pointer"
                      >
                        <RefreshCw className="w-3 h-3 mr-1" />
                        {t.conversation.buttons.retry}
                      </button>
                    )}
                  </div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Fixed Bottom Input Dock Area */}
          <div className="shrink-0 p-3 sm:p-4 bg-white/95 backdrop-blur-xs border-t border-slate-200/90 shadow-2xs">
            {/* Compact Quick Prompts Bar */}
            {!isSubmitted && !isCancelled && (
              <div className="mb-2 flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
                <span className="text-[11px] text-slate-400 shrink-0 font-medium">快捷提示：</span>
                {t.conversation.quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleSendMessage(prompt)}
                    disabled={isSending || isLoadingConv}
                    className="px-2.5 py-0.8 rounded-full bg-white/90 border border-slate-200 hover:border-indigo-300 hover:text-indigo-600 text-slate-600 text-[11px] font-medium whitespace-nowrap shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {/* Composer Input Box */}
            {isSubmitted ? (
              <div className="p-3.5 rounded-2xl bg-white border border-slate-200 text-center shadow-card space-y-1">
                <p className="text-xs font-bold text-slate-800">
                  {t.conversation.input.submittedNotice}
                </p>
                <p className="text-[11px] text-slate-500">
                  {t.conversation.input.submittedSubtext}
                </p>
              </div>
            ) : isCancelled ? (
              <div className="p-3 rounded-2xl bg-white border border-slate-200 text-center shadow-card">
                <p className="text-xs text-slate-500">{t.conversation.input.cancelledNotice}</p>
              </div>
            ) : (
              <form onSubmit={handleFormSubmit} className="surface-floating rounded-2xl p-1.5 sm:p-2 border border-slate-200/90 flex flex-col space-y-1">
                {/* Active Listening Audio Wave Indicator */}
                {isListening && (
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium animate-pulse">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    <span>正在语音录入中... 请描述故障现象，完成后再次点击麦克风</span>
                    <div className="flex items-center space-x-1 ml-auto">
                      <span className="w-1 h-3 bg-rose-500 animate-pulse" />
                      <span className="w-1 h-4 bg-rose-500 animate-pulse" />
                      <span className="w-1 h-2.5 bg-rose-500 animate-pulse" />
                    </div>
                  </div>
                )}

                {/* Speech Error Banner */}
                {speechError && (
                  <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                      <span>{speechError}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSpeechError(null)}
                      className="text-amber-700 hover:text-amber-900 text-xs font-bold ml-2 cursor-pointer"
                    >
                      知道了
                    </button>
                  </div>
                )}

                <div className="flex items-end space-x-1.5 px-2 pt-1">
                  <textarea
                    ref={textareaRef}
                    rows={2}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder={isListening ? '正在语音识别转写中...' : t.conversation.input.placeholder}
                    disabled={isSending || isLoadingConv}
                    className="flex-1 bg-transparent border-none text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-0 resize-none max-h-24"
                  />
                  {/* Microphone speech recognition trigger button */}
                  <button
                    type="button"
                    onClick={toggleSpeechRecognition}
                    disabled={isSending || isLoadingConv}
                    className={`inline-flex items-center justify-center p-2.5 rounded-xl transition-all disabled:opacity-40 shrink-0 cursor-pointer mb-0.5 ${
                      isListening
                        ? 'bg-rose-500 hover:bg-rose-600 text-white shadow-md animate-pulse ring-2 ring-rose-400/50'
                        : 'bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 text-slate-600 border border-slate-200/80'
                    }`}
                    title={isListening ? '点击停止语音录入' : '点击开启语音录入报修'}
                  >
                    {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>

                  <button
                    type="submit"
                    disabled={!inputText.trim() || isSending || isLoadingConv}
                    className="inline-flex items-center justify-center p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-all disabled:opacity-40 shrink-0 cursor-pointer mb-0.5"
                    title={t.conversation.input.sendTitle}
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
                <div className="px-2 pb-1 text-[10px] text-slate-400 flex items-center justify-between">
                  <span>Enter 发送 · Shift + Enter 换行 · 支持麦克风实时语音输入</span>
                  {inputText.length > 0 && <span>{inputText.length} 字</span>}
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Desktop Request Intelligence Panel (~32%) */}
        <div className="hidden lg:block lg:col-span-4 surface-elevated rounded-2xl p-5 sticky top-20">
          {renderIntelligencePanel()}
        </div>
      </div>

      {/* History Drawer Side Sheet */}
      <Drawer
        isOpen={showHistoryDrawer}
        onClose={() => setShowHistoryDrawer(false)}
        title={t.conversation.buttons.recentConversations}
        subtitle="历史智能受理会话记录"
        width="md"
      >
        <div className="space-y-2 py-2">
          {conversationsList.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setSearchParams({ id: item.id.toString() });
                setShowHistoryDrawer(false);
              }}
              className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between text-xs cursor-pointer ${
                conversation?.id === item.id
                  ? 'bg-indigo-50/90 border-indigo-300 text-indigo-950 font-semibold shadow-2xs'
                  : 'bg-white border-slate-200/80 text-slate-700 hover:bg-slate-50'
              }`}
            >
              <div className="truncate mr-2">
                <span className="block font-semibold text-slate-900 truncate">
                  {item.draft_preview || `对话 #${item.id}`}
                </span>
                <span className="text-[11px] text-slate-400 mt-0.5 block font-mono">
                  {formatDateTimeZh(item.created_at)}
                </span>
              </div>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold shrink-0 ${
                  item.status === 'submitted'
                    ? 'bg-sky-100 text-sky-800'
                    : item.status === 'awaiting_confirmation'
                    ? 'bg-emerald-100 text-emerald-800'
                    : item.status === 'cancelled'
                    ? 'bg-slate-200 text-slate-600'
                    : 'bg-indigo-100 text-indigo-800'
                }`}
              >
                {item.status === 'submitted'
                  ? t.conversation.draft.statusSubmitted
                  : item.status === 'awaiting_confirmation'
                  ? t.conversation.draft.statusReady
                  : item.status === 'cancelled'
                  ? t.conversation.draft.statusCancelled
                  : '正在收集'}
              </span>
            </button>
          ))}
        </div>
      </Drawer>

      {/* Mobile Drawer Sheet for Draft Review */}
      <Drawer
        isOpen={showMobileDraftSheet}
        onClose={() => setShowMobileDraftSheet(false)}
        title={t.conversation.draft.title}
        subtitle="核对并提交当前维修需求"
        width="md"
      >
        <div className="py-2">
          {renderIntelligencePanel()}
        </div>
      </Drawer>

      {/* Cancel Confirmation Dialog */}
      <Dialog
        isOpen={showCancelDialog}
        onClose={() => setShowCancelDialog(false)}
        title={t.conversation.cancelDialog.title}
        description={t.conversation.cancelDialog.description}
        variant="danger"
        confirmLabel={t.conversation.cancelDialog.confirmLabel}
        cancelLabel={t.conversation.cancelDialog.cancelLabel}
        isLoading={isCancelling}
        onConfirm={confirmCancelConversation}
      />
    </div>
  );
};
