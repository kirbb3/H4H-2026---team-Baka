// PolicyDetailModal.tsx
// Full-screen modal that shows the complete details of a single policy.
//
// Sections (top to bottom):
//   1. Blue gradient header with status badge and policy title
//   2. Category pill
//   3. Metadata grid — department, published date, effective date, closing date, funding
//   4. Summary paragraph
//   5. Details section (eligibility + funding text, only when different from summary)
//   6. Implementation date banner — green if known, yellow if not yet announced
//   7. Tags
//   8. Action buttons — Find Out More, Apply Now (optional), Bookmark, Bell
//
// Props:
//   policy      — the policy to display, or null (modal won't render)
//   isOpen      — controls Dialog visibility
//   onClose     — called when the user dismisses the modal
//   isSaved     — whether the current user has bookmarked this policy
//   onSave      — toggles the bookmark (requires login)
//   isLoggedIn  — disables bookmark/bell when false
//   isSubscribed— whether the user is subscribed to email alerts
//   onSubscribe — toggles the email subscription (requires login)

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Badge } from "./ui/badge";
import { Clock, Building2, X, Bookmark, BookmarkCheck, Bell } from "lucide-react";
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
  memo_url?: string | null;    // direct staff-memorandum PDF (most specific gov doc)
  source_url?: string | null;  // broader meeting agenda page (fallback)
  funding_amount?: string | null;
  funding_pct_diff?: string | null;
}

interface PolicyDetailModalProps {
  policy: Policy | null;
  isOpen: boolean;
  onClose: () => void;
  isSaved?: boolean;
  onSave?: () => void;
  isLoggedIn?: boolean;
  isSubscribed?: boolean;
  onSubscribe?: () => void;
}

export function PolicyDetailModal({
  policy, isOpen, onClose,
  isSaved, onSave, isLoggedIn,
  isSubscribed, onSubscribe,
}: PolicyDetailModalProps) {
  // Short CSS animation states — triggered on click and auto-reset after a short delay.
  const [bellAnim, setBellAnim] = useState(false);
  const [bookmarkAnim, setBookmarkAnim] = useState(false);

  // Don't render anything if no policy is selected.
  if (!policy) return null;

  // ── Color maps ─────────────────────────────────────────────────────────────
  // Unused currently but kept for future priority badge use.
  const priorityColors: Record<string, string> = {
    Critical: "bg-red-100 text-red-800 border-red-200",
    High:     "bg-orange-100 text-orange-800 border-orange-200",
    Medium:   "bg-blue-100 text-blue-800 border-blue-200",
    Low:      "bg-gray-100 text-gray-800 border-gray-200"
  };

  // Background + text colour for the status badge in the header.
  const statusColors: Record<string, string> = {
    Active:        "bg-green-100 text-green-800",
    Proposed:      "bg-yellow-100 text-yellow-800",
    "Under Review":"bg-blue-100 text-blue-800",
    Archived:      "bg-gray-100 text-gray-800"
  };

  /** Format an ISO or US date string into a human-readable form, e.g. "March 1, 2026". */
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr; // return as-is if unparseable
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  };

  /** Trigger the bookmark action with a brief pop animation. */
  const handleBookmarkClick = () => {
    if (!isLoggedIn || !onSave) return;
    setBookmarkAnim(true);
    setTimeout(() => setBookmarkAnim(false), 400);
    onSave();
  };

  /** Trigger the subscription toggle with a brief bell-ring animation. */
  const handleBellClick = () => {
    if (!isLoggedIn || !onSubscribe) return;
    setBellAnim(true);
    setTimeout(() => setBellAnim(false), 600);
    onSubscribe();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto p-0">

        {/* Floating close button — overlays the blue header */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2 hover:bg-white transition-colors shadow-lg"
        >
          <X className="w-5 h-5" />
        </button>

        {/* ── Blue gradient header ───────────────────────────────────────── */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-8 text-white">
          <div className="flex gap-2 mb-4">
            {/* Status badge — colour reflects whether the policy is active, proposed, etc. */}
            <Badge className={statusColors[policy.status]}>{policy.status}</Badge>
          </div>
          <DialogHeader>
            <DialogTitle className="text-3xl font-bold text-white leading-tight">
              {policy.title}
            </DialogTitle>
          </DialogHeader>
        </div>

        <div className="p-8">
          {/* Category pill — e.g. "Rental Assistance", "Homebuyer" */}
          <div className="mb-6">
            <span className="inline-block px-4 py-1.5 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              {policy.category}
            </span>
          </div>

          {/* ── Metadata grid ──────────────────────────────────────────────── */}
          {/* Shows at most 4 cells depending on which fields are populated.   */}
          <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
            {/* Department — always present */}
            <div className="flex items-center gap-2 text-gray-700">
              <Building2 className="w-5 h-5 text-gray-400" />
              <div>
                <div className="text-xs text-gray-500">Department</div>
                <div className="font-medium">{policy.department}</div>
              </div>
            </div>

            {/* Published date — date of the council meeting where it was discussed */}
            <div className="flex items-center gap-2 text-gray-700">
              <Clock className="w-5 h-5 text-gray-400" />
              <div>
                <div className="text-xs text-gray-500">Published</div>
                <div className="font-medium">{formatDate(policy.date)}</div>
              </div>
            </div>

            {/* Effective date — only shown when the scraper extracted one from the memo */}
            {policy.effective_date && (
              <div className="flex items-center gap-2 text-gray-700">
                <Clock className="w-5 h-5 text-green-500" />
                <div>
                  <div className="text-xs text-gray-500">Effective Date</div>
                  <div className="font-medium text-green-700">{policy.effective_date}</div>
                </div>
              </div>
            )}

            {/* Closing/deadline date — shown in red to convey urgency */}
            {policy.closing_date && (
              <div className="flex items-center gap-2 text-gray-700">
                <Clock className="w-5 h-5 text-red-400" />
                <div>
                  <div className="text-xs text-gray-500">Closes / Deadline</div>
                  <div className="font-medium text-red-700">{policy.closing_date}</div>
                </div>
              </div>
            )}

            {/* Funding — shown with a relative-to-average label when available */}
            {policy.funding_amount && (
              <div className="flex items-center gap-2 text-gray-700">
                <div>
                  <div className="text-xs text-gray-500">Funding</div>
                  <div className="font-medium">{policy.funding_amount}</div>
                  {/* funding_pct_diff is a string like "+46% above average" */}
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

          {/* ── Summary ────────────────────────────────────────────────────── */}
          <div className="mb-6">
            <h3 className="font-semibold text-lg mb-3 text-gray-900">Summary</h3>
            <p className="text-gray-700 text-lg leading-relaxed">{policy.summary}</p>
          </div>

          {/* ── Details ─────────────────────────────────────────────────────── */}
          {/* The "content" field appends eligibility + funding text to the summary.
              Only render this section when there's genuinely extra content. */}
          {policy.content && policy.content !== policy.summary && (
            <div className="mb-6">
              <h3 className="font-semibold text-lg mb-3 text-gray-900">Details</h3>
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">{policy.content}</p>
            </div>
          )}

          {/* ── Implementation date banner ───────────────────────────────────
              Green = date known (extracted by scraper from the memorandum).
              Yellow = policy approved but no implementation date announced yet. */}
          {policy.effective_date ? (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-green-800 text-sm">
                <strong>Implementation Date:</strong> This policy takes effect on <strong>{policy.effective_date}</strong>.
              </p>
            </div>
          ) : (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-yellow-800 text-sm">
                <strong>Future Policy:</strong> This policy has been approved but an implementation date has not yet been announced. Keep it in mind as it may affect you when details are released.
              </p>
            </div>
          )}

          {/* ── Tags ────────────────────────────────────────────────────────── */}
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

          {/* ── Action buttons ──────────────────────────────────────────────── */}
          <div className="flex gap-3">
            {/* "Find Out More" — links to the government document for this policy.
                Prefers memo_url (the specific staff memorandum PDF) over source_url
                (the broader agenda page).  Hidden when neither is available. */}
            {(policy.memo_url || policy.source_url) && (
              <Button
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                onClick={() => window.open((policy.memo_url || policy.source_url)!, "_blank")}
              >
                Find Out More
              </Button>
            )}

            {/* Bookmark button — saves the policy to the user's account.
                Dimmed when not logged in; shows a filled icon when already saved. */}
            <Button
              variant="outline"
              onClick={handleBookmarkClick}
              title={isLoggedIn ? (isSaved ? "Remove from saved" : "Save this policy") : "Sign in to save policies"}
              className={`px-4 transition-colors ${isSaved ? "border-blue-500 text-blue-600 hover:bg-blue-50" : "text-gray-500 hover:text-blue-600"} ${!isLoggedIn ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <span className={`inline-block ${bookmarkAnim ? "animate-bookmark-pop" : ""}`}>
                {isSaved ? <BookmarkCheck className="w-5 h-5" /> : <Bookmark className="w-5 h-5" />}
              </span>
            </Button>

            {/* Bell button — subscribes the user to email notifications for this policy.
                Amber when subscribed, neutral otherwise. Dimmed when not logged in. */}
            <Button
              variant="outline"
              onClick={handleBellClick}
              title={isLoggedIn ? (isSubscribed ? "Unsubscribe from notifications" : "Get email notifications for this policy") : "Sign in to enable notifications"}
              className={`px-4 transition-all ${
                isSubscribed
                  ? "bg-amber-50 border-amber-400 text-amber-600 hover:bg-amber-100"
                  : "text-gray-500 hover:text-amber-600 hover:border-amber-300"
              } ${!isLoggedIn ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <span className={`inline-block ${bellAnim ? "animate-bell-ring" : ""}`}>
                <Bell className={`w-5 h-5 ${isSubscribed ? "fill-amber-400" : ""}`} />
              </span>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
