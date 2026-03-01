import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Badge } from "./ui/badge";
import { Clock, Building2, X } from "lucide-react";
import { Button } from "./ui/button";

interface Policy {
  id: string;
  title: string;
  summary: string;
  category: string;
  department: string;
  date: string;
  status: string;
  priority: string;
  content: string;
  tags: string[];
  apply_url?: string | null;
  effective_date?: string | null;
  closing_date?: string | null;
  source_url?: string | null;
  funding_amount?: string | null;
  funding_pct_diff?: string | null;
}

interface PolicyDetailModalProps {
  policy: Policy | null;
  isOpen: boolean;
  onClose: () => void;
}

export function PolicyDetailModal({ policy, isOpen, onClose }: PolicyDetailModalProps) {
  if (!policy) return null;

  const priorityColors: Record<string, string> = {
    critical: "bg-red-100 text-red-800 border-red-200",
    high: "bg-orange-100 text-orange-800 border-orange-200",
    medium: "bg-blue-100 text-blue-800 border-blue-200",
    low: "bg-gray-100 text-gray-800 border-gray-200"
  };

  const statusColors: Record<string, string> = {
    Active: "bg-green-100 text-green-800",
    Proposed: "bg-yellow-100 text-yellow-800",
    "Under Review": "bg-blue-100 text-blue-800",
    Archived: "bg-gray-100 text-gray-800"
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto p-0">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2 hover:bg-white transition-colors shadow-lg"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-8 text-white">
          <div className="flex gap-2 mb-4">
            <Badge className={statusColors[policy.status]}>{policy.status}</Badge>
            <Badge className={priorityColors[policy.priority]}>{policy.priority}</Badge>
          </div>
          <DialogHeader>
            <DialogTitle className="text-3xl font-bold text-white leading-tight">
              {policy.title}
            </DialogTitle>
          </DialogHeader>
        </div>

        <div className="p-8">
          <div className="mb-6">
            <span className="inline-block px-4 py-1.5 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              {policy.category}
            </span>
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 text-gray-700">
              <Building2 className="w-5 h-5 text-gray-400" />
              <div>
                <div className="text-xs text-gray-500">Department</div>
                <div className="font-medium">{policy.department}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-gray-700">
              <Clock className="w-5 h-5 text-gray-400" />
              <div>
                <div className="text-xs text-gray-500">Published</div>
                <div className="font-medium">{formatDate(policy.date)}</div>
              </div>
            </div>
            {policy.effective_date && (
              <div className="flex items-center gap-2 text-gray-700">
                <Clock className="w-5 h-5 text-green-500" />
                <div>
                  <div className="text-xs text-gray-500">Effective Date</div>
                  <div className="font-medium text-green-700">{policy.effective_date}</div>
                </div>
              </div>
            )}
            {policy.closing_date && (
              <div className="flex items-center gap-2 text-gray-700">
                <Clock className="w-5 h-5 text-red-400" />
                <div>
                  <div className="text-xs text-gray-500">Closes / Deadline</div>
                  <div className="font-medium text-red-700">{policy.closing_date}</div>
                </div>
              </div>
            )}
            {policy.funding_amount && (
              <div className="flex items-center gap-2 text-gray-700">
                <div>
                  <div className="text-xs text-gray-500">Funding</div>
                  <div className="font-medium">{policy.funding_amount}</div>
                  {policy.funding_pct_diff && (
                    <div className={`text-xs font-medium mt-0.5 ${
                      policy.funding_pct_diff.startsWith("+") ? "text-green-600" :
                      policy.funding_pct_diff.startsWith("≈") ? "text-gray-500" :
                      "text-red-500"
                    }`}>
                      {policy.funding_pct_diff}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="mb-6">
            <h3 className="font-semibold text-lg mb-3 text-gray-900">Summary</h3>
            <p className="text-gray-700 text-lg leading-relaxed">{policy.summary}</p>
          </div>

          {policy.content && policy.content !== policy.summary && (
            <div className="mb-6">
              <h3 className="font-semibold text-lg mb-3 text-gray-900">Details</h3>
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">{policy.content}</p>
            </div>
          )}

          {!policy.effective_date && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-yellow-800 text-sm">
                <strong>Future Policy:</strong> This policy has been approved but an implementation date has not yet been announced. Keep it in mind as it may affect you when details are released.
              </p>
            </div>
          )}

          <div className="mb-6">
            <h3 className="font-semibold text-lg mb-3 text-gray-900">Tags</h3>
            <div className="flex flex-wrap gap-2">
              {policy.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            {policy.apply_url ? (
              <Button
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                onClick={() => window.open(policy.apply_url!, "_blank")}
              >
                Apply Now
              </Button>
            ) : (
              <Button className="flex-1" disabled>
                Application Link Coming Soon
              </Button>
            )}
            {policy.source_url && (
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => window.open(policy.source_url!, "_blank")}
              >
                View Source Document
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
