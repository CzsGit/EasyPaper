import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Download, Loader2, FileText, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

const Reader = () => {
    const { taskId } = useParams<{ taskId: string }>();
    const navigate = useNavigate();
    const [status, setStatus] = useState<string>("loading");
    const [originalPdfUrl, setOriginalPdfUrl] = useState<string | null>(null);
    const [resultPdfUrl, setResultPdfUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [focusMode, setFocusMode] = useState(() => window.innerWidth < 768);
    const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Track mobile breakpoint and auto-enable focus mode
    useEffect(() => {
        const onResize = () => {
            const mobile = window.innerWidth < 768;
            setIsMobile(mobile);
            if (mobile) setFocusMode(true);
        };
        window.addEventListener("resize", onResize);
        return () => window.removeEventListener("resize", onResize);
    }, []);

    useEffect(() => {
        let cancelled = false;

        const fetchStatus = async () => {
            try {
                const response = await api.get(`/api/status/${taskId}`);
                if (cancelled) return;
                setStatus(response.data.status);

                if (response.data.status === "completed") {
                    const [originalResponse, resultResponse] = await Promise.all([
                        api.get(`/api/original/${taskId}/pdf`, { responseType: "blob" }),
                        api.get(`/api/result/${taskId}/pdf`, { responseType: "blob" }),
                    ]);
                    if (cancelled) return;

                    setOriginalPdfUrl(URL.createObjectURL(new Blob([originalResponse.data], { type: "application/pdf" })));
                    setResultPdfUrl(URL.createObjectURL(new Blob([resultResponse.data], { type: "application/pdf" })));
                    setLoading(false);
                } else if (response.data.status === "failed" || response.data.status === "error") {
                    setLoading(false);
                } else {
                    timeoutRef.current = setTimeout(fetchStatus, 2000);
                }
            } catch {
                if (cancelled) return;
                setLoading(false);
                setStatus("error");
            }
        };

        fetchStatus();

        return () => {
            cancelled = true;
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, [taskId]);

    // Cleanup blob URLs on unmount
    useEffect(() => {
        return () => {
            if (originalPdfUrl) URL.revokeObjectURL(originalPdfUrl);
            if (resultPdfUrl) URL.revokeObjectURL(resultPdfUrl);
        };
    }, [originalPdfUrl, resultPdfUrl]);

    const handleDownload = () => {
        if (resultPdfUrl) {
            const link = document.createElement("a");
            link.href = resultPdfUrl;
            link.setAttribute("download", `simplified_${taskId}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
        }
    };

    if (loading || status === "processing" || status === "pending" || status === "parsing" || status === "rewriting" || status === "rendering") {
        return (
            <div className="flex h-[calc(100vh-4rem)] flex-col items-center justify-center space-y-4">
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <p className="text-lg font-medium text-muted-foreground">
                    {["processing", "parsing", "rewriting", "rendering"].includes(status)
                        ? "AI is processing your document..."
                        : "Loading..."}
                </p>
            </div>
        );
    }

    if (status === "failed" || status === "error") {
        return (
            <div className="flex h-[calc(100vh-4rem)] flex-col items-center justify-center space-y-4">
                <div className="rounded-full bg-red-100 p-4 text-red-600">
                    <FileText className="h-8 w-8" />
                </div>
                <h2 className="text-xl font-semibold">Processing Failed</h2>
                <p className="text-muted-foreground">Something went wrong while processing this document.</p>
                <Button onClick={() => navigate("/dashboard")}>Back to Dashboard</Button>
            </div>
        );
    }

    return (
        <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
            {/* Toolbar */}
            <div className="flex items-center justify-between rounded-xl border bg-white p-3 shadow-sm">
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")}>
                        <ArrowLeft className="mr-2 h-4 w-4" />
                        Back
                    </Button>
                    <div className="h-4 w-px bg-gray-200 mx-2 hidden sm:block" />
                    <h1 className="text-sm font-medium text-gray-900 hidden sm:block">Document Reader</h1>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setFocusMode(!focusMode)}
                        className={cn("gap-2", focusMode && "bg-primary/10 text-primary border-primary/20")}
                    >
                        <Sparkles className="h-4 w-4" />
                        <span className="hidden sm:inline">{focusMode ? "Show Original" : "Focus Mode"}</span>
                    </Button>
                    <Button size="sm" onClick={handleDownload} className="gap-2">
                        <Download className="h-4 w-4" />
                        <span className="hidden sm:inline">Download PDF</span>
                    </Button>
                </div>
            </div>

            {/* Split Pane */}
            <ResizablePanelGroup
                direction={isMobile ? "vertical" : "horizontal"}
                className="min-h-0 flex-1 rounded-xl border bg-white shadow-sm overflow-hidden"
                style={{ direction: "ltr" }}
            >
                {/* Left Panel: AI Simplified PDF */}
                <ResizablePanel defaultSize={focusMode ? 100 : 50} minSize={30}>
                    <div className="flex h-full flex-col bg-white">
                        <div className="flex items-center justify-between border-b bg-white px-4 py-2">
                            <div className="flex items-center gap-2">
                                <Sparkles className="h-3 w-3 text-primary" />
                                <span className="text-xs font-medium text-primary uppercase tracking-wider">AI Result (PDF)</span>
                            </div>
                        </div>
                        <div className="flex-1 bg-gray-100/50">
                            {resultPdfUrl && (
                                <iframe
                                    src={resultPdfUrl}
                                    className="h-full w-full border-none"
                                    title="Simplified PDF"
                                />
                            )}
                        </div>
                    </div>
                </ResizablePanel>

                {/* Right Panel: Original PDF - Hidden in Focus Mode */}
                {!focusMode && (
                    <>
                        <ResizableHandle withHandle />
                        <ResizablePanel defaultSize={50} minSize={30}>
                            <div className="flex h-full flex-col">
                                <div className="flex items-center justify-between border-b bg-gray-50/50 px-4 py-2">
                                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Original Source (PDF)</span>
                                </div>
                                <div className="flex-1 bg-gray-100/50">
                                    {originalPdfUrl && (
                                        <iframe
                                            src={originalPdfUrl}
                                            className="h-full w-full border-none"
                                            title="Original PDF"
                                        />
                                    )}
                                </div>
                            </div>
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};

export default Reader;
