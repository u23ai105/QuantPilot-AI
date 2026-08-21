import { useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { documentsApi } from "@/lib/api/resources";
import type { DocumentResponse } from "@/lib/api/resources";
import { FileText, UploadCloud, Trash2, Search, Loader2, AlertCircle } from "lucide-react";

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "PROCESSED" ? "bg-emerald-500/10 text-emerald-500" :
    status === "FAILED"    ? "bg-destructive/10 text-destructive" :
                             "bg-amber-500/10 text-amber-500";
  return <span className={`text-xs px-2 py-1 rounded font-medium ${color}`}>{status}</span>;
}

export function DocumentsPage() {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: docs = [], isLoading, error } = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsApi.list(),
    refetchInterval: 5000, // poll so PROCESSING → PROCESSED updates automatically
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentsApi.upload(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => documentsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
      e.target.value = "";
    }
  };

  const formatSize = (bytes: number) =>
    bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <PageContainer title="Documents & RAG" description="Upload 10-K / annual-report PDFs for AI context retrieval.">
      {/* Search + Upload Row */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search documents..." className="pl-9 bg-background/50" disabled />
        </div>
        <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
        <Button
          className="bg-foreground text-background hover:bg-foreground/90"
          disabled={uploadMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploadMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <UploadCloud className="h-4 w-4 mr-2" />
          )}
          Upload PDF
        </Button>
      </div>

      {uploadMutation.isError && (
        <div className="mb-4 flex items-center gap-2 text-destructive text-sm bg-destructive/10 rounded-lg p-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {(uploadMutation.error as Error).message}
        </div>
      )}

      {/* Document Grid */}
      {isLoading && (
        <div className="flex items-center gap-2 text-muted-foreground text-sm py-12 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading documents...
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm py-12 justify-center">
          <AlertCircle className="h-4 w-4" /> Failed to load documents
        </div>
      )}
      {!isLoading && docs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground border border-dashed border-border/50 rounded-lg">
          <FileText className="h-10 w-10 opacity-20 mb-3" />
          <p className="text-sm">No documents yet.</p>
          <p className="text-xs mt-1">Upload a 10-K or annual report PDF to get started.</p>
        </div>
      )}

      {docs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {docs.map((doc: DocumentResponse) => (
            <Card key={doc.id} className="bg-background/50 border-border/50 hover:border-ai/30 transition-colors">
              <CardHeader className="flex flex-row items-start justify-between pb-2">
                <FileText className="h-8 w-8 text-muted-foreground" />
                <div className="flex items-center gap-2">
                  <StatusBadge status={doc.status} />
                  <button
                    onClick={() => deleteMutation.mutate(doc.id)}
                    disabled={deleteMutation.isPending}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                <CardTitle className="text-sm font-medium truncate mb-2">{doc.filename}</CardTitle>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">{formatSize(doc.file_size)}</p>
                  {doc.page_count != null && (
                    <p className="text-xs text-muted-foreground">{doc.page_count} pages</p>
                  )}
                  {doc.status === "PROCESSING" && (
                    <p className="text-xs text-amber-500 flex items-center gap-1">
                      <Loader2 className="h-3 w-3 animate-spin" /> Extracting text &amp; embedding vectors...
                    </p>
                  )}
                  {doc.status === "FAILED" && doc.error_message && (
                    <p className="text-xs text-destructive truncate">{doc.error_message}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
