import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, BookOpen, Download, FileText, Loader2, Menu, MessageCircleQuestion, PanelRight, Search, X } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";

type Mode = "chinese" | "simple" | "original" | "bilingual";
type Block = { id: string; page: number; type: string; source_text: string; index: number };
type Section = { id: string; title: string; block_id: string; page: number };
type Workspace = { task_id: string; task_mode?: string; paper_id: string; document: { title: string; page_count: number; blocks: Block[]; sections: Section[]; warnings: string[] }; state: { block_id: string; offset: number; mode: Mode; font_size: number }; pdf_status: string; pdf_message: string; percent?: number; has_result: boolean; has_dual: boolean };

const modes: { id: Mode; label: string; hint: string }[] = [
  { id: "chinese", label: "中文译文", hint: "完整译文" },
  { id: "simple", label: "简化英文", hint: "易读英文" },
  { id: "original", label: "原文", hint: "原始排版" },
  { id: "bilingual", label: "双语对照", hint: "原文 + 译文" },
];

export default function Reader() {
  const { taskId = "" } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [mode, setMode] = useState<Mode>("chinese");
  const [outlineOpen, setOutlineOpen] = useState(true);
  const [askOpen, setAskOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [selection, setSelection] = useState("");
  const [answer, setAnswer] = useState<{ answer?: string; reasoning?: string; uncertainty?: string; evidence_refs?: { page: number; quote: string }[] } | null>(null);
  const [asking, setAsking] = useState(false);
  const [search, setSearch] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const urlRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    api.get(`/api/reading/${taskId}`).then(({ data }) => {
      if (cancelled) return;
      setWorkspace(data); setMode(data.state.mode || "chinese");
      const current = data.document.blocks.find((b: Block) => b.id === data.state.block_id);
      setPage(current?.page || 1);
    }).catch((err) => !cancelled && setError(getApiErrorMessage(err, "无法打开论文")));
    return () => { cancelled = true; };
  }, [taskId]);

  useEffect(() => {
    if (!workspace || workspace.has_result) return;
    const timer = window.setInterval(() => {
      void api.get(`/api/status/${taskId}`).then(({ data }) => setWorkspace((old) => old ? { ...old, pdf_status: data.status || old.pdf_status, pdf_message: data.message || old.pdf_message, percent: data.percent, has_result: data.has_result ?? old.has_result, has_dual: data.has_dual_pdf ?? old.has_dual } : old));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [taskId, workspace?.has_result]);

  useEffect(() => {
    if (!workspace) return;
    const useResult = mode !== "original";
    const format = mode === "bilingual" && workspace.has_dual ? "dual" : "mono";
    if (useResult && !workspace.has_result) { setPdfUrl(""); return; }
    let cancelled = false;
    setPdfLoading(true);
    const endpoint = useResult ? `/api/result/${taskId}/pdf?format=${format}` : `/api/original/${taskId}/pdf`;
    api.get(endpoint, { responseType: "blob" }).then(({ data }) => {
      if (cancelled) return;
      const next = URL.createObjectURL(data); if (urlRef.current) URL.revokeObjectURL(urlRef.current); urlRef.current = next; setPdfUrl(next);
    }).catch((err) => !cancelled && toast.error(getApiErrorMessage(err, "PDF 加载失败"))).finally(() => !cancelled && setPdfLoading(false));
    return () => { cancelled = true; };
  }, [taskId, mode, workspace?.has_result, workspace?.has_dual]);

  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }, []);

  const results = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!workspace || !q) return [];
    return workspace.document.blocks.filter((b) => b.source_text.toLowerCase().includes(q)).slice(0, 30);
  }, [workspace, search]);
  const setPosition = (block: Block) => {
    setPage(block.page); setSearch("");
    setWorkspace((old) => old ? { ...old, state: { ...old.state, block_id: block.id } } : old);
    void api.patch(`/api/reading/${taskId}/state`, { block_id: block.id, offset: 0 }).catch(() => undefined);
  };
  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true); setAnswer(null);
    try { const { data } = await api.post(`/api/reading/${taskId}/ask`, { question, selection }); setAnswer(data); }
    catch (err) { toast.error(getApiErrorMessage(err, "提问失败，请重试")); }
    finally { setAsking(false); }
  };
  const download = async (format: "mono" | "dual") => {
    try { const { data } = await api.get(`/api/result/${taskId}/pdf?format=${format}`, { responseType: "blob" }); const link = document.createElement("a"); link.href = URL.createObjectURL(data); link.download = `${format === "dual" ? "bilingual" : "translated"}-${taskId}.pdf`; link.click(); }
    catch (err) { toast.error(getApiErrorMessage(err, "文件尚未生成")); }
  };

  if (error) return <main className="reader-empty"><FileText size={40} /><h1>无法打开论文</h1><p>{error}</p><Button onClick={() => navigate("/dashboard")}>返回文档库</Button></main>;
  if (!workspace) return <main className="reader-empty"><Loader2 className="spin" size={30} /><p>正在打开论文…</p></main>;
  const current = workspace.document.blocks.find((b) => b.id === workspace.state.block_id);
  const visibleSections = workspace.document.sections.filter((s, i) => i === 0 || /^(?:[1-9](?:\.\d+)*|[A-Z])\s/.test(s.title) || s.title === "References");
  const hasTranslation = workspace.has_result;
  const availableModes = modes.filter((item) => item.id !== "simple" || workspace.task_mode === "simplify");
  return <div className="reader-workspace">
    <header className="reader-topbar">
      <div className="reader-brand"><Button variant="ghost" size="icon" aria-label="返回文档库" onClick={() => navigate("/dashboard")}><ArrowLeft size={18} /></Button><div><p className="reader-kicker">连续阅读</p><h1 title={workspace.document.title}>{workspace.document.title}</h1></div></div>
      <div className="reader-controls"><div className="mode-switch" role="group" aria-label="阅读版本"><BookOpen size={16} />{availableModes.map((item) => <button key={item.id} className={mode === item.id ? "active" : ""} onClick={() => { setMode(item.id); void api.patch(`/api/reading/${taskId}/state`, { mode: item.id }); }}>{item.label}</button>)}</div><span className="reader-page">第 {current?.page || page} / {workspace.document.page_count} 页</span><Button variant="outline" size="sm" onClick={() => setAskOpen((v) => !v)}><MessageCircleQuestion size={16} /><span className="desktop-label">全文提问</span></Button><Button variant="outline" size="sm" onClick={() => setOutlineOpen((v) => !v)}><Menu size={16} /><span className="desktop-label">目录</span></Button><Button variant="outline" size="sm" disabled={!hasTranslation} onClick={() => void download("mono")}><Download size={16} /><span className="desktop-label">下载译文</span></Button></div>
    </header>
    {!hasTranslation && <div className="reader-status"><Loader2 className="spin" size={17} /><span>{workspace.pdf_message || "译文正在生成。你可以先阅读完整原文，完成后会自动出现译文。"}</span><strong>{workspace.pdf_status} {workspace.percent ? `${workspace.percent}%` : ""}</strong></div>}
    <div className="reader-layout">
      {outlineOpen && <aside className="outline-rail"><div className="rail-head"><span>目录</span><button onClick={() => setOutlineOpen(false)} aria-label="关闭目录"><X size={18} /></button></div><div className="reader-search"><Search size={15} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索全文" /></div>{search && <nav className="search-results">{results.map((b) => <button key={b.id} onClick={() => setPosition(b)}><b>第 {b.page} 页</b><span>{b.source_text.slice(0, 90)}</span></button>)}</nav>} {!search && <nav>{visibleSections.map((s) => <button key={s.id} onClick={() => setPosition(workspace.document.blocks.find((b) => b.id === s.block_id) || { ...s, type: "heading", source_text: "", index: 0 })}><span>{s.title}</span><small>第 {s.page} 页</small></button>)}</nav>}<div className="rail-foot">正文按原始页面连续呈现，译文不会拆成卡片。</div></aside>}
      <main className="pdf-reading"><div className="pdf-frame-wrap">{pdfLoading && <div className="pdf-loading"><Loader2 className="spin" size={22} />正在加载完整页面…</div>}{pdfUrl ? <iframe key={`${mode}-${pdfUrl}`} title={mode === "original" ? "论文原文" : "论文译文"} src={`${pdfUrl}#page=${page}`} className="pdf-frame" /> : <div className="pdf-empty"><FileText size={34} /><p>{hasTranslation || mode === "original" ? "正在准备 PDF…" : "译文尚未完成，请先阅读原文"}</p></div>}</div></main>
      {askOpen && <aside className="assistant-panel"><div className="assistant-head"><div><p className="reader-kicker">整篇论文</p><h2>遇到问题时再问 AI</h2></div><button onClick={() => setAskOpen(false)} aria-label="关闭提问"><X size={18} /></button></div><div className="assistant-body"><p className="assistant-note">AI 会使用整篇论文作为上下文。正文始终保留完整原文和译文。</p><textarea value={selection} onChange={(e) => setSelection(e.target.value)} placeholder="可粘贴选中的原文（可选）" /><textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="例如：作者如何证明这个方法有效？" onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void ask(); }} /><Button onClick={() => void ask()} disabled={asking || !question.trim()}>{asking ? <Loader2 className="spin" size={16} /> : <MessageCircleQuestion size={16} />}提问全文</Button>{answer && <div className="answer"><h3>回答</h3><p>{answer.answer}</p>{answer.reasoning && <><h4>依据</h4><p>{answer.reasoning}</p></>}{answer.uncertainty && <p className="uncertainty">{answer.uncertainty}</p>}{answer.evidence_refs?.length ? <div className="answer-evidence">{answer.evidence_refs.map((r, i) => <button key={i} onClick={() => setPage(r.page)}>第 {r.page} 页：{r.quote.slice(0, 80)}</button>)}</div> : null}</div>}</div></aside>}
    </div>
  </div>;
}
