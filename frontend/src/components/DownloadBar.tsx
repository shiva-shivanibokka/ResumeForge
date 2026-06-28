import { downloadUrl } from "../lib/api";
import { Button } from "./ui";

// Download links for a generated artifact (PDF inline-previewable, DOCX as file).
export function DownloadBar({
  pdfId,
  docxId,
  pdfName,
  docxName,
}: {
  pdfId: string | null;
  docxId: string | null;
  pdfName?: string | null;
  docxName?: string | null;
}) {
  if (!pdfId && !docxId) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {pdfId && (
        <a href={downloadUrl(pdfId)} target="_blank" rel="noopener noreferrer">
          <Button variant="forge" type="button">
            ⬇ PDF{pdfName ? ` · ${pdfName}` : ""}
          </Button>
        </a>
      )}
      {docxId && (
        <a href={downloadUrl(docxId)}>
          <Button variant="ghost" type="button">
            ⬇ DOCX{docxName ? ` · ${docxName}` : ""}
          </Button>
        </a>
      )}
    </div>
  );
}

export function PdfPreview({ pdfId, title }: { pdfId: string | null; title: string }) {
  if (!pdfId) return null;
  return (
    <div className="overflow-hidden rounded-[10px] border border-steel bg-white">
      <iframe
        title={title}
        src={downloadUrl(pdfId)}
        className="h-[640px] w-full"
        style={{ border: "none" }}
      />
    </div>
  );
}
