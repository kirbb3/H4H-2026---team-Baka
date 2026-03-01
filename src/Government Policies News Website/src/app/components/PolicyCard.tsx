import { Badge } from "./ui/badge";
import { Clock, Building2 } from "lucide-react";

interface Policy {
  id: string;
  title: string;
  summary: string;
  category: string;
  department: string;
  date: string;
  status: string;
  priority: string;
  tags: string[];
  targeted_labels?: string[];
  funding_amount?: string | null;
  funding_pct_diff?: string | null;
}

interface PolicyCardProps {
  policy: Policy;
  variant?: "default" | "featured" | "compact";
  onClick?: () => void;
}

export function PolicyCard({ policy, variant = "default", onClick }: PolicyCardProps) {
  const priorityColors: Record<string, string> = {
    Critical: "bg-red-100 text-red-800 border-red-200",
    High: "bg-orange-100 text-orange-800 border-orange-200",
    Medium: "bg-blue-100 text-blue-800 border-blue-200",
    Low: "bg-gray-100 text-gray-800 border-gray-200"
  };

  const statusColors: Record<string, string> = {
    Active: "bg-green-100 text-green-800",
    Proposed: "bg-yellow-100 text-yellow-800",
    Archived: "bg-gray-100 text-gray-800"
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  if (variant === "featured") {
    return (
      <div
        onClick={onClick}
        className="group relative overflow-hidden rounded-2xl bg-white shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer border border-gray-100 col-span-full"
      >
        <div className="p-8">
          <div className="flex flex-wrap gap-2 mb-4">
            <Badge className={statusColors[policy.status]}>{policy.status}</Badge>
            {policy.targeted_labels?.map((label) => (
              <Badge key={label} className="bg-purple-100 text-purple-800 border-purple-200">{label}</Badge>
            ))}
          </div>
          <div className="text-sm font-medium text-blue-600 mb-2">{policy.category}</div>
          <h2 className="text-3xl font-bold mb-4 text-gray-900 group-hover:text-blue-600 transition-colors">
            {policy.title}
          </h2>
          <p className="text-gray-600 text-lg mb-6 line-clamp-3">{policy.summary}</p>
          <div className="flex flex-wrap gap-2 mb-6">
            {policy.tags.map((tag) => (
              <span key={tag} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                {tag}
              </span>
            ))}
          </div>
          <div className="flex gap-6 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              <span>{policy.department}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4" />
              <span>{formatDate(policy.date)}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <div
        onClick={onClick}
        className="group bg-white rounded-xl p-6 shadow-sm hover:shadow-lg transition-all duration-300 cursor-pointer border border-gray-100"
      >
        <div className="flex justify-between items-start mb-3">
          <Badge className={statusColors[policy.status]} variant="outline">
            {policy.status}
          </Badge>
          <span className="text-xs text-gray-500">{formatDate(policy.date)}</span>
        </div>
        {policy.targeted_labels && policy.targeted_labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {policy.targeted_labels.map((label) => (
              <Badge key={label} className="bg-purple-100 text-purple-800 border-purple-200 text-xs">{label}</Badge>
            ))}
          </div>
        )}
        <div className="text-xs font-medium text-blue-600 mb-2">{policy.category}</div>
        <h3 className="font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors line-clamp-2">
          {policy.title}
        </h3>
        <p className="text-sm text-gray-600 line-clamp-2 mb-3">{policy.summary}</p>
        <div className="text-xs text-gray-500 flex items-center gap-1">
          <Building2 className="w-3 h-3" />
          <span className="truncate">{policy.department}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      className="group bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer border border-gray-100"
    >
      <div className="p-6">
        <div className="flex justify-between items-start mb-3">
          <span className="text-xs font-medium text-blue-600">{policy.category}</span>
          <div className="flex gap-2">
            <Badge className={statusColors[policy.status]} variant="outline">
              {policy.status}
            </Badge>
          </div>
        </div>
        {policy.targeted_labels && policy.targeted_labels.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {policy.targeted_labels.map((label) => (
              <Badge key={label} className="bg-purple-100 text-purple-800 border-purple-200 text-xs">{label}</Badge>
            ))}
          </div>
        )}
        <h3 className="text-xl font-semibold mb-3 text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
          {policy.title}
        </h3>
        <p className="text-gray-600 mb-4 line-clamp-3">{policy.summary}</p>
        <div className="flex flex-col gap-2 text-sm text-gray-500 border-t pt-4">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4" />
            <span className="truncate">{policy.department}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            <span>{formatDate(policy.date)}</span>
          </div>
          {policy.funding_amount && (
            <div className="flex items-center justify-between">
              <span className="font-medium text-gray-700">{policy.funding_amount}</span>
              {policy.funding_pct_diff && (
                <span className={`text-xs font-medium ${
                  policy.funding_pct_diff.startsWith("+") ? "text-green-600" :
                  policy.funding_pct_diff.startsWith("≈") ? "text-gray-400" :
                  "text-red-500"
                }`}>
                  {policy.funding_pct_diff}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
