import { PageContainer } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, UploadCloud, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function DocumentsPage() {
  const mockDocs = [
    { id: "doc_1", filename: "AAPL_10K_2023.pdf", status: "PROCESSED", chunks: 342 },
    { id: "doc_2", filename: "TSLA_Q3_2023.pdf", status: "PROCESSING", chunks: 0 },
  ];

  return (
    <PageContainer title="Documents & RAG" description="Upload financial documents for AI context retrieval.">
      <div className="flex gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search documents..." className="pl-9 bg-background/50" />
        </div>
        <Button className="bg-foreground text-background hover:bg-foreground/90">
          <UploadCloud className="h-4 w-4 mr-2" />
          Upload PDF
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockDocs.map(doc => (
          <Card key={doc.id} className="bg-background/50 border-border/50 hover:border-ai/50 transition-colors cursor-pointer">
            <CardHeader className="flex flex-row items-start justify-between pb-2">
              <FileText className="h-8 w-8 text-muted-foreground" />
              <div className={`text-xs px-2 py-1 rounded font-medium ${
                doc.status === 'PROCESSED' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'
              }`}>
                {doc.status}
              </div>
            </CardHeader>
            <CardContent>
              <CardTitle className="text-sm font-medium truncate mb-1">{doc.filename}</CardTitle>
              <p className="text-xs text-muted-foreground">
                {doc.chunks > 0 ? `${doc.chunks} embedded chunks` : "Extracting text and vectors..."}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </PageContainer>
  );
}
