import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft, BookOpen, Check, ChevronRight, Download, ExternalLink,
  FileText, Highlighter, Lightbulb, Loader2, Menu, MessageCircleQuestion,
  NotebookPen, PanelRight, RefreshCw, Sparkles, X, ZoomIn,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// The reader speaks in blocks. Every generated answer points back to one of these IDs.
type Mode = "chinese" | "simple" | "original" | "bilingual";
type BlockType = "paragraph" | "heading" | "figure" | "table" | "equation" | "caption" | "scan";
interface Sentence { id: string; text: string; start: number; end: number }
interface Block { id: string; index: number; page: number; section_id: string; type: BlockType; source_text: string; bbox: number[]; sentences: Sentence[]; rows?: string[][] }
interface Section { id: string; title: string; block_id: string; page: number }
interface Term { term: string; meaning: string; definition: string }
interface Aid { chinese: string; simple_english: string; explanation: string; terms: Term[]; variables: Term[]; reading_guide: string; uncertainty: string; evidence_refs?: { block_id: string; page: number; quote: string }[] }
interface Workspace { task_id: string; paper_id: string; document: { title: string; page_count: number; sections: Section[]; blocks: Block[]; warnings: string[] }; aids: Record<string, Aid>; state: { block_id: string; offset: number; mode: Mode; font_size: number; understood: string[]; bookmarked_terms: string[] }; notes: { id: string; content: string; target_id: string; type: string; created_at: string }[]; knowledge_status: string; knowledge_error?: string; pdf_status: string; pdf_message: string; has_result: boolean; has_dual: boolean; highlights: { stats?: { total: number }; status?: string; sentences: { sentence_id: string; page_index: number; text: string }[] } }

const modeLabels: Record<Mode, string> = { chinese: "中文", simple: "简化英文", original: "原文", bilingual: "双语" };
const typeLabels: Record<BlockType, string> = { paragraph: "段落", heading: "章节", figure: "图", table: "表", equation: "公式", caption: "图注", scan: "扫描页" };

function isTextBlock(block: Block) { return ["paragraph", "heading", "caption"].includes(block.type); }

export default function Reader() {
  const { taskId = "" } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [mode, setMode] = useState<Mode>("chinese");
  const [fontSize, setFontSize] = useState(18);
  const [activeId, setActiveId] = useState("");
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [assistantTab, setAssistantTab] = useState<"explain" | "terms" | "evidence" | "notes" | "summary" | "highlights">("explain");
  const [explainQuestion, setExplainQuestion] = useState("");
  const [explainSelection, setExplainSelection] = useState("");
  const [explanation, setExplanation] = useState<{ answer: string; background?: string; uncertainty?: string; evidence_refs?: { block_id: string; page: number; quote: string }[] } | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const blockRefs = useRef(new Map<string, HTMLElement>());
  const readingRef = useRef<HTMLElement | null>(null);
  const didRestore = useRef(false);
  const saveTimer = useRef<number>();
  const pendingAids = useRef(new Set<string>());

  const activeBlock = useMemo(() => workspace?.document.blocks.find((b) => b.id === activeId) || workspace?.document.blocks[0], [workspace, activeId]);
  const readerDocument = workspace?.document;
  const savedBlockId = workspace?.state.block_id;
  const activeAid = activeBlock && workspace?.aids[activeBlock.id];
  const sections = workspace?.document.sections || [];

  const saveState = useCallback((patch: Partial<Workspace["state"]>) => {
    if (!taskId) return;
    setWorkspace((current) => current ? { ...current, state: { ...current.state, ...patch } } : current);
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      void api.patch(`/api/reading/${taskId}/state`, patch).catch(() => undefined);
    }, 450);
  }, [taskId]);

  const loadAid = useCallback(async (block: Block) => {
    if (block.type === "heading" || pendingAids.current.has(block.id)) return;
    pendingAids.current.add(block.id);
    try {
      const response = await api.post(`/api/reading/${taskId}/blocks/${block.id}/aid`);
      setWorkspace((current) => current ? { ...current, aids: { ...current.aids, [block.id]: response.data } } : current);
    } catch { /* The original remains available; the block renders a retry action. */ }
    finally { pendingAids.current.delete(block.id); }
  }, [taskId]);

  useEffect(() => {
    let cancelled = false;
    api.get(`/api/reading/${taskId}`).then((response) => {
      if (cancelled) return;
      const next = response.data as Workspace;
      setWorkspace(next); setMode(next.state.mode); setFontSize(next.state.font_size);
      setActiveId(next.state.block_id || next.document.blocks[0]?.id || "");
    }).catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "无法打开论文"); });
    return () => { cancelled = true; window.clearTimeout(saveTimer.current); };
  }, [taskId]);

  useEffect(() => {
    if (!readerDocument) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) {
        const id = (visible.target as HTMLElement).dataset.blockId || "";
        setActiveId(id); saveState({ block_id: id, offset: readingRef.current?.scrollTop || 0 });
        const block = readerDocument?.blocks.find((item) => item.id === id);
        if (block) void loadAid(block);
      }
    }, { rootMargin: "-18% 0px -64% 0px", threshold: [0.1, 0.5] });
    blockRefs.current.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [readerDocument, loadAid, saveState]);

  useEffect(() => {
    if (!readerDocument || didRestore.current) return;
    if (savedBlockId) blockRefs.current.get(savedBlockId)?.scrollIntoView({ behavior: "auto", block: "start" });
    didRestore.current = true;
  }, [readerDocument, savedBlockId]);

  useEffect(() => {
    if (!readerDocument || !activeBlock) return;
    const index = activeBlock.index;
    readerDocument.blocks.slice(Math.max(0, index - 1), index + 3).forEach((block) => void loadAid(block));
  }, [readerDocument, activeBlock, loadAid]);

  const jump = (id: string) => {
    blockRefs.current.get(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(id); setOutlineOpen(false); saveState({ block_id: id });
  };

  const requestExplanation = async () => {
    if (!activeBlock || !explainQuestion.trim()) return;
    setBusy("explain"); setExplanation(null);
    try {
      const response = await api.post(`/api/reading/${taskId}/blocks/${activeBlock.id}/explain`, { question: explainQuestion, selection: explainSelection });
      setExplanation(response.data); setAssistantTab("explain");
    } catch (err: unknown) { toast.error(getApiErrorMessage(err, "解释生成失败，请重试")); }
    finally { setBusy(""); }
  };

  const requestSummary = async () => {
    setBusy("summary");
    try { const response = await api.post(`/api/reading/${taskId}/summary`); setSummary(response.data); setAssistantTab("summary"); }
    catch (err: unknown) { toast.error(getApiErrorMessage(err, "摘要生成失败，请重试")); }
    finally { setBusy(""); }
  };

  useEffect(() => {
    if (!workspace) return;
    const requested = searchParams.get("block");
    if (requested && workspace.document.blocks.some((block) => block.id === requested)) jump(requested);
    if (searchParams.get("panel") === "summary") { setAssistantOpen(true); void requestSummary(); }
    // The query is an entry deep-link, not a live dependency of the reading loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace?.document, searchParams]);

  const addNote = async () => {
    if (!activeBlock || !explainSelection.trim() || !workspace) return;
    setBusy("note");
    try {
      const response = await api.post(`/api/knowledge/papers/${workspace.paper_id}/annotations`, { type: "note", content: explainSelection, target_type: "block", target_id: activeBlock.id });
      setWorkspace((current) => current ? { ...current, notes: [response.data, ...current.notes] } : current);
      setExplainSelection(""); toast.success("笔记已保存"); setAssistantTab("notes");
    } catch (err: unknown) { toast.error(getApiErrorMessage(err, "笔记保存失败")); }
    finally { setBusy(""); }
  };

  const download = async (format: "mono" | "dual") => {
    setBusy(format);
    try { const response = await api.get(`/api/result/${taskId}/pdf?format=${format}`, { responseType: "blob" }); const url = URL.createObjectURL(response.data); const link = document.createElement("a"); link.href = url; link.download = `${format === "dual" ? "bilingual" : "translated"}-${taskId}.pdf`; link.click(); URL.revokeObjectURL(url); }
    catch { toast.error("文件尚未生成或下载失败"); }
    finally { setBusy(""); }
  };

  if (error) return <main className="reader-empty"><FileText size={42} /><h1>无法打开论文</h1><p>{error}</p><Button onClick={() => navigate("/dashboard")}>返回文档库</Button></main>;
  if (!workspace) return <main className="reader-empty"><Loader2 className="spin" size={34} /><p>正在准备可读版本…</p></main>;

  const currentIndex = activeBlock ? activeBlock.index + 1 : 0;
  const understood = workspace.state.understood.includes(activeBlock?.id || "");
  const setModeAndSave = (next: Mode) => { setMode(next); saveState({ mode: next }); };
  const evidence = explanation?.evidence_refs || activeAid?.evidence_refs || [];

  return <div className="reader-workspace">
    <header className="reader-topbar">
      <div className="reader-brand"><Button variant="ghost" size="icon" aria-label="返回文档库" onClick={() => navigate("/dashboard")}><ArrowLeft size={18} /></Button><div><p className="reader-kicker">正在阅读</p><h1 title={workspace.document.title}>{workspace.document.title}</h1></div></div>
      <div className="reader-controls">
        <div className="mode-switch" role="group" aria-label="阅读语言"><BookOpen size={16} />{(Object.keys(modeLabels) as Mode[]).map((item) => <button key={item} className={cn(item === mode && "active")} onClick={() => setModeAndSave(item)}>{modeLabels[item]}</button>)}</div>
        <div className="reader-progress"><span>{currentIndex}/{workspace.document.blocks.length} 段</span><div><i style={{ width: `${Math.max(2, currentIndex / workspace.document.blocks.length * 100)}%` }} /></div></div>
        <div className="font-controls" aria-label="阅读字号"><button aria-label="减小字号" onClick={() => { const next = Math.max(16, fontSize - 1); setFontSize(next); saveState({ font_size: next }); }}>A−</button><button aria-label="增大字号" onClick={() => { const next = Math.min(24, fontSize + 1); setFontSize(next); saveState({ font_size: next }); }}>A＋</button></div>
        <Button variant="outline" size="sm" onClick={() => setAssistantOpen((value) => !value)} aria-label="打开辅助面板"><PanelRight size={16} /><span className="desktop-label">辅助</span></Button>
        <Button variant="outline" size="sm" onClick={() => setOutlineOpen(true)} aria-label="打开论文目录"><Menu size={16} /><span className="desktop-label">目录</span></Button>
        <div className="reader-downloads"><Button variant="outline" size="sm" onClick={() => void download("mono")} disabled={!workspace.has_result || Boolean(busy)}><Download size={16} /><span className="desktop-label">PDF</span></Button>{workspace.has_dual && <Button variant="outline" size="sm" onClick={() => void download("dual")} disabled={Boolean(busy)}><Download size={16} /><span className="desktop-label">双语 PDF</span></Button>}</div>
      </div>
    </header>
    <div className="reader-layout">
      <aside className={cn("outline-rail", outlineOpen && "mobile-open")}><div className="rail-head"><span>目录</span><button className="mobile-close" onClick={() => setOutlineOpen(false)} aria-label="关闭目录"><X size={18} /></button></div><nav>{sections.map((section) => <button key={section.id} className={cn(section.block_id === activeId && "active")} onClick={() => jump(section.block_id)}><span>{section.title}</span><small>第 {section.page} 页</small></button>)}</nav><div className="rail-foot"><span>已读 {workspace.state.understood.length} 段</span><span>{workspace.knowledge_status === "completed" ? "知识已提取" : "可随时提取知识"}</span></div></aside>
      <main ref={readingRef} className="reading-scroll" style={{ "--reading-size": `${fontSize}px` } as React.CSSProperties}><div className="reading-intro"><p className="reader-kicker">论文地图</p><h2>先理解问题，再跟着证据读完</h2><p>切换语言不会改变位置。遇到术语、公式或图表，打开右侧辅助面板；每条解释都带回原文证据。</p>{workspace.document.warnings.length > 0 && <div className="reader-warning"><Lightbulb size={16} />{workspace.document.warnings[0]}</div>}</div>{workspace.document.blocks.map((block) => { const aid = workspace.aids[block.id]; const isActive = activeId === block.id; return <article key={block.id} data-block-id={block.id} ref={(node) => { if (node) blockRefs.current.set(block.id, node); else blockRefs.current.delete(block.id); }} className={cn("reading-block", `block-${block.type}`, isActive && "active", understood && isActive && "understood")}>
        <div className="block-meta"><span>{typeLabels[block.type]}</span><span>第 {block.page} 页</span>{isActive && <span className="now-reading">正在阅读</span>}</div>
        {block.type === "heading" ? <h3>{block.source_text}</h3> : <>
          {isTextBlock(block) && (mode === "original" || mode === "bilingual") && <p className="source-copy" lang="en">{block.source_text}</p>}
          {block.type === "table" && <div className="source-table">{(block.rows || []).map((row, i) => <div key={i}>{row.map((cell, j) => <span key={j}>{cell}</span>)}</div>)}</div>}
          {(block.type === "figure" || block.type === "equation" || block.type === "scan") && <FigurePreview taskId={taskId} block={block} />}
          {block.type === "equation" && <p className="equation-copy">{block.source_text || "公式（请查看原始证据）"}</p>}
          {mode !== "original" && (aid ? <div className="translated-copy">{mode === "simple" ? aid.simple_english : aid.chinese}</div> : <div className="aid-pending"><Loader2 className="spin" size={16} /><span>正在准备这一段的辅助内容…</span><button onClick={() => void loadAid(block)}><RefreshCw size={14} />重试</button></div>)}
          {isActive && <div className="block-actions"><button onClick={() => { setAssistantTab("explain"); setAssistantOpen(true); }}><MessageCircleQuestion size={15} />解释这段</button><button onClick={() => { setExplainSelection(block.source_text); setAssistantTab("explain"); setAssistantOpen(true); }}><NotebookPen size={15} />写笔记</button><button onClick={() => saveState({ understood: understood ? workspace.state.understood.filter((id) => id !== block.id) : [...workspace.state.understood, block.id] })}><Check size={15} />{understood ? "取消已理解" : "标记已理解"}</button></div>}
          {aid?.explanation && isActive && <p className="inline-guide"><Sparkles size={15} />{aid.explanation}</p>}
          {aid?.reading_guide && isActive && <p className="inline-guide figure-guide"><Lightbulb size={15} />{aid.reading_guide}</p>}
          {aid?.uncertainty && isActive && <p className="inline-uncertainty">需要核对：{aid.uncertainty}</p>}
        </>}
      </article>; })}<footer className="reading-finish"><Check size={20} /><div><h3>读到这里了</h3><p>继续完成章节后，可以在右侧生成摘要、提取知识和复习卡。</p></div><Button variant="outline" onClick={() => void requestSummary()} disabled={Boolean(busy)}>{busy === "summary" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}生成论文地图</Button></footer></main>
      {assistantOpen && <aside className="assistant-panel"><div className="assistant-head"><div><p className="reader-kicker">当前段落</p><h2>{activeBlock ? `第 ${activeBlock.page} 页 · ${typeLabels[activeBlock.type]}` : "选择一段开始"}</h2></div><button className="mobile-close" onClick={() => setAssistantOpen(false)} aria-label="关闭辅助面板"><X size={18} /></button></div><div className="assistant-tabs">{(["explain", "terms", "evidence", "notes", "summary", "highlights"] as const).map((tab) => <button key={tab} className={cn(assistantTab === tab && "active")} onClick={() => tab === "summary" ? void requestSummary() : setAssistantTab(tab)}>{({ explain: "解释", terms: "术语", evidence: "证据", notes: "笔记", summary: "地图", highlights: "高亮" } as Record<string, string>)[tab]}</button>)}</div><div className="assistant-body">
        {assistantTab === "explain" && <><div className="context-quote">{activeBlock?.source_text || "选中正文后，辅助内容会出现在这里。"}</div>{explanation && <div className="answer"><h3>解释</h3><p>{explanation.answer}</p>{explanation.background && <p className="muted">{explanation.background}</p>}{explanation.uncertainty && <p className="inline-uncertainty">{explanation.uncertainty}</p>}</div>}<label className="assistant-label" htmlFor="question">你想弄懂什么？</label><Input id="question" placeholder="例如：这一步为什么能提高准确率？" value={explainQuestion} onChange={(event) => setExplainQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void requestExplanation(); }} /><label className="assistant-label" htmlFor="selection">选中的原文或笔记</label><textarea id="selection" value={explainSelection} onChange={(event) => setExplainSelection(event.target.value)} placeholder="可粘贴一个词、一句话或保留为空" /><Button onClick={() => void requestExplanation()} disabled={Boolean(busy) || !explainQuestion.trim()}>{busy === "explain" ? <Loader2 className="spin" size={16} /> : <MessageCircleQuestion size={16} />}解释这段</Button></>}
        {assistantTab === "terms" && <TermList aid={activeAid} onSelect={(term) => { setExplainSelection(term.term); setExplainQuestion(`这个术语在本文中是什么意思？`); setAssistantTab("explain"); }} />}
        {assistantTab === "evidence" && <EvidenceList taskId={taskId} block={activeBlock} evidence={evidence} />}
        {assistantTab === "notes" && <><div className="context-quote">笔记会绑定到当前段落，之后可从知识库和 Obsidian 导出。</div><textarea value={explainSelection} onChange={(event) => setExplainSelection(event.target.value)} placeholder="写下你的理解、疑问或下一步" /><Button onClick={() => void addNote()} disabled={Boolean(busy) || !explainSelection.trim()}><NotebookPen size={16} />保存笔记</Button>{workspace.notes.filter((note) => !note.target_id || note.target_id === activeBlock?.id).map((note) => <div className="saved-note" key={note.id}>{note.content}</div>)}</>}
        {assistantTab === "summary" && <SummaryView data={summary} busy={busy === "summary"} onJump={jump} />}
        {assistantTab === "highlights" && <HighlightList workspace={workspace} onJump={(page) => { const block = workspace.document.blocks.find((item) => item.page === page); if (block) jump(block.id); }} />}
      </div></aside>}
    </div>
    <div className="reader-bottomline"><span>{workspace.pdf_status === "completed" ? "PDF 版本已就绪" : `PDF：${workspace.pdf_message}`}</span><span>位置会自动保存</span>{workspace.knowledge_status !== "completed" && <button onClick={async () => { setBusy("knowledge"); try { await api.post(`/api/knowledge/extract/${taskId}`); toast.success("知识提取已开始"); } catch { toast.error("知识提取启动失败"); } finally { setBusy(""); } }} disabled={Boolean(busy)}><Sparkles size={14} />提取知识</button>}</div>
  </div>;
}

function FigurePreview({ taskId, block }: { taskId: string; block: Block }) {
  const [src, setSrc] = useState(""); const [zoom, setZoom] = useState(false);
  useEffect(() => { let cancelled = false; let url = ""; api.get(`/api/reading/${taskId}/blocks/${block.id}/source`, { responseType: "blob" }).then((response) => { url = URL.createObjectURL(response.data); if (!cancelled) setSrc(url); }).catch(() => undefined); return () => { cancelled = true; if (url) URL.revokeObjectURL(url); }; }, [taskId, block.id]);
  return <div className={cn("figure-preview", zoom && "zoomed")}><div className="figure-toolbar"><span>{block.type === "equation" ? "原始公式" : "原始图表"}</span><button onClick={() => setZoom((value) => !value)} aria-label="放大图表"><ZoomIn size={15} /></button></div>{src ? <img src={src} alt={block.source_text || "论文图表原图"} /> : <div className="image-pending"><Loader2 className="spin" size={16} />加载原图…</div>}</div>;
}

function TermList({ aid, onSelect }: { aid?: Aid; onSelect: (term: Term) => void }) { return <div className="term-list">{aid?.terms?.length ? aid.terms.map((term) => <button key={term.term} onClick={() => onSelect(term)}><strong>{term.term}</strong><span>{term.meaning}</span><small>{term.definition}</small></button>) : <div className="assistant-empty"><BookOpen size={24} /><p>这一段还没有术语解释。</p><small>先等待辅助内容，或在“解释”中询问一个术语。</small></div>}</div>; }
function EvidenceList({ taskId, block, evidence }: { taskId: string; block?: Block; evidence: { block_id: string; page: number; quote: string }[] }) { const [source, setSource] = useState(""); const [fullPage, setFullPage] = useState(false); useEffect(() => { if (!block) return; let cancelled = false; let url = ""; api.get(`/api/reading/${taskId}/blocks/${block.id}/source?full_page=${fullPage}`, { responseType: "blob" }).then((response) => { url = URL.createObjectURL(response.data); if (!cancelled) setSource(url); }).catch(() => undefined); return () => { cancelled = true; if (url) URL.revokeObjectURL(url); }; }, [taskId, block, fullPage]); return <div className="evidence-list"><p className="context-quote">所有生成内容只显示它能支持的原文。</p>{evidence.map((item) => <div className="evidence-item" key={item.block_id}><span>第 {item.page} 页</span><p>{item.quote || "图像证据，请查看原图"}</p></div>)}{block && <><button className="evidence-toggle" onClick={() => setFullPage((value) => !value)}><ExternalLink size={14} />{fullPage ? "查看段落裁剪" : "查看整页原文"}</button>{source && <img className="evidence-image" src={source} alt={`第 ${block.page} 页原文证据`} />}</>}</div>; }
function SummaryView({ data, busy, onJump }: { data: Record<string, unknown> | null; busy: boolean; onJump: (id: string) => void }) { if (busy) return <div className="assistant-empty"><Loader2 className="spin" size={24} /><p>正在阅读全文并建立论文地图…</p></div>; if (!data) return <div className="assistant-empty"><Sparkles size={24} /><p>摘要会带着证据回到正文。</p></div>; const story = data.story as Record<string, { text?: string; evidence_refs?: { block_id: string }[] }> | undefined; return <div className="summary-view"><h3>{String(data.one_liner || "论文地图")}</h3>{story && Object.entries(story).map(([key, value]) => <div key={key}><strong>{{ problem: "问题", method: "方法", results: "结果", impact: "意义" }[key] || key}</strong><p>{value.text}</p>{value.evidence_refs?.map((ref) => <button key={ref.block_id} onClick={() => onJump(ref.block_id)}>查看原文 <ChevronRight size={14} /></button>)}</div>)}</div>; }
function HighlightList({ workspace, onJump }: { workspace: Workspace; onJump: (page: number) => void }) { const sentences = workspace.highlights.sentences || []; return <div className="highlight-list">{sentences.length ? sentences.map((sentence) => <button key={sentence.sentence_id} onClick={() => onJump(sentence.page_index + 1)}><Highlighter size={14} /><span>第 {sentence.page_index + 1} 页</span><p>{sentence.text}</p></button>) : <div className="assistant-empty"><Highlighter size={24} /><p>没有可用的高亮句子。</p><small>导入时开启 AI 高亮，或直接从当前段落开始阅读。</small></div>}</div>; }
