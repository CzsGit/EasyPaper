import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Upload, FileText, ArrowRight, Clock, CheckCircle, AlertCircle, Languages, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

interface Task {
    task_id: string;
    filename: string;
    status: "pending" | "processing" | "parsing" | "rewriting" | "rendering" | "completed" | "failed";
    created_at: string;
    percent?: number;
    message?: string;
    mode?: "translate" | "simplify";
}

const Dashboard = () => {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [mode, setMode] = useState<"translate" | "simplify">("translate");
    const navigate = useNavigate();

    const fetchTasks = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await axios.get("/api/tasks", {
                headers: { "Authorization": `Bearer ${token}` }
            });
            setTasks(response.data);
        } catch (error) {
            console.error("Failed to fetch tasks", error);
        }
    };

    useEffect(() => {
        fetchTasks();
        // Poll for updates every 2 seconds
        const interval = setInterval(fetchTasks, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;

        // Handle multiple files if needed, currently just one at a time but non-blocking
        const file = e.target.files[0];
        // Reset input immediately to allow selecting the same file again or another file quickly
        e.target.value = "";

        const formData = new FormData();
        formData.append("file", file);
        formData.append("mode", mode);

        // Optimistically add task or just let polling catch it?
        // For better UX, we could add a temporary "uploading" item, but simply unblocking is the first step.
        // Let's just fire the request and let the user continue.

        try {
            const token = localStorage.getItem("token");
            await axios.post("/api/upload", formData, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            // Trigger immediate fetch
            fetchTasks();

        } catch (error) {
            console.error("Upload failed", error);
            alert("Upload failed.");
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "completed": return "text-green-600 bg-green-50 border-green-200";
            case "processing":
            case "parsing":
            case "rewriting":
            case "rendering":
                return "text-blue-600 bg-blue-50 border-blue-200";
            case "failed": return "text-red-600 bg-red-50 border-red-200";
            default: return "text-gray-600 bg-gray-50 border-gray-200";
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "completed": return <CheckCircle className="h-4 w-4" />;
            case "processing":
            case "parsing":
            case "rewriting":
            case "rendering":
                return <Clock className="h-4 w-4 animate-pulse" />;
            case "failed": return <AlertCircle className="h-4 w-4" />;
            default: return <Clock className="h-4 w-4" />;
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Hero Section */}
            <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary/5 via-primary/10 to-transparent p-8 md:p-12 text-center border border-primary/10 shadow-sm">
                <div className="relative z-10 mx-auto max-w-2xl space-y-6">
                    <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
                        EasyPaper
                    </h1>
                    <p className="text-lg text-gray-600">
                        Upload your English academic papers. Translate to Chinese or simplify
                        complex vocabulary — while preserving layout, images, and formulas.
                    </p>

                    {/* Mode Selector */}
                    <div className="flex justify-center gap-3">
                        <button
                            onClick={() => setMode("translate")}
                            className={cn(
                                "flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all",
                                mode === "translate"
                                    ? "bg-primary text-primary-foreground shadow-md"
                                    : "bg-white/80 text-gray-600 border border-gray-200 hover:bg-gray-50"
                            )}
                        >
                            <Languages className="h-4 w-4" />
                            Translate to Chinese
                        </button>
                        <button
                            onClick={() => setMode("simplify")}
                            className={cn(
                                "flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all",
                                mode === "simplify"
                                    ? "bg-primary text-primary-foreground shadow-md"
                                    : "bg-white/80 text-gray-600 border border-gray-200 hover:bg-gray-50"
                            )}
                        >
                            <BookOpen className="h-4 w-4" />
                            Simplify English
                        </button>
                    </div>

                    <div className="flex justify-center pt-2">
                        <Label
                            htmlFor="file-upload"
                            className={cn(
                                "group relative flex cursor-pointer items-center justify-center gap-3 rounded-full bg-primary px-8 py-4 text-lg font-medium text-primary-foreground shadow-lg transition-all hover:bg-primary/90 hover:shadow-xl hover:scale-105 active:scale-95"
                            )}
                        >
                            <Upload className="h-5 w-5" />
                            <span>Upload PDF</span>
                            <Input
                                id="file-upload"
                                type="file"
                                accept=".pdf"
                                className="hidden"
                                onChange={handleUpload}
                            />
                        </Label>
                    </div>
                </div>

                {/* Decorative background elements */}
                <div className="absolute top-0 left-0 -translate-x-1/2 -translate-y-1/2 h-64 w-64 rounded-full bg-blue-200/30 blur-3xl" />
                <div className="absolute bottom-0 right-0 translate-x-1/2 translate-y-1/2 h-64 w-64 rounded-full bg-purple-200/30 blur-3xl" />
            </section>

            {/* Task List */}
            <section className="space-y-4">
                <div className="flex items-center justify-between px-2">
                    <h2 className="text-2xl font-semibold tracking-tight">Recent Documents</h2>
                </div>

                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {tasks.map((task) => (
                        <Card key={task.task_id} className="group relative overflow-hidden transition-all hover:shadow-md border-gray-200/60">
                            <CardHeader className="pb-3">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 text-gray-500 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                                            <FileText className="h-5 w-5" />
                                        </div>
                                        <div className="space-y-1">
                                            <CardTitle className="text-base font-medium leading-none line-clamp-1" title={task.filename}>
                                                {task.filename}
                                            </CardTitle>
                                            <CardDescription className="text-xs flex items-center gap-1.5">
                                                {new Date(task.created_at).toLocaleDateString()}
                                                <span className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
                                                    {task.mode === "simplify" ? "Simplify" : "Translate"}
                                                </span>
                                            </CardDescription>
                                        </div>
                                    </div>
                                    <div className={cn("flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium border", getStatusColor(task.status))}>
                                        {getStatusIcon(task.status)}
                                        <span className="capitalize">{task.status}</span>
                                    </div>
                                </div>
                            </CardHeader>

                            <CardContent>
                                <div className="space-y-3">
                                    {["processing", "parsing", "rewriting", "rendering"].includes(task.status) && (
                                        <div className="space-y-1.5">
                                            <div className="flex justify-between text-xs text-muted-foreground">
                                                <span>{task.message || "Processing..."}</span>
                                                <span>{task.percent || 0}%</span>
                                            </div>
                                            <Progress value={task.percent || 0} className="h-1.5" />
                                        </div>
                                    )}

                                    {task.status === "completed" && (
                                        <Button
                                            className="w-full gap-2 group-hover:bg-primary group-hover:text-primary-foreground"
                                            variant="outline"
                                            onClick={() => navigate(`/reader/${task.task_id}`)}
                                        >
                                            Read Document
                                            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                                        </Button>
                                    )}

                                    {task.status === "failed" && (
                                        <p className="text-xs text-red-500">
                                            {task.message || "Processing failed"}
                                        </p>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}

                    {tasks.length === 0 && (
                        <div className="col-span-full py-12 text-center text-muted-foreground bg-gray-50/50 rounded-xl border border-dashed">
                            <p>No documents yet. Upload one to get started!</p>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
};

export default Dashboard;
