// App.tsx
// Root component for GovPolicy Hub.
//
// Responsibilities:
//   - Fetches housing programs from the Flask backend (/api/policies) whenever
//     the user changes their filter selections.
//   - Deduplicates the returned programs client-side (word-set similarity).
//   - Applies text search and sort order client-side (no extra network round-trip).
//   - Manages saved-policy and subscription state, syncing with the backend
//     when the user is logged in.
//   - Renders the sticky header, hero banner with search bar, policy grid,
//     detail modal, and footer.

import { useState, useMemo, useEffect, useRef } from "react";
import { FileText, TrendingUp, AlertCircle, Bookmark, ChevronDown } from "lucide-react";
import { PolicyCard } from "./components/PolicyCard";
import { SearchBar } from "./components/SearchBar";
import { PolicyDetailModal } from "./components/PolicyDetailModal";
import { UserMenu } from "./components/UserMenu";
import { Toast } from "./components/Toast";
import { useAuth } from "../AuthContext";

// Shape of a single policy as returned by the Flask /api/policies endpoint.
interface Policy {
  id: string;
  title: string;
  summary: string;
  category: string;
  department: string;
  date: string;           // ISO date string, e.g. "2024-12-16"
  status: string;         // "Active" | "Proposed" | "Under Review" | etc.
  priority: string;       // "High" | "Medium"
  content: string;        // extended text: summary + eligibility + funding
  tags: string[];
  apply_url?: string | null;
  effective_date?: string | null;
  closing_date?: string | null;
  source_url?: string | null;    // link to the city council agenda page
  funding_amount?: string | null;
  funding_pct_diff?: string | null; // e.g. "+46% above average"
  benefit_type?: string;
  targeted_labels?: string[];    // populated when profile filters are active
}

// Shape of the filter panel state.
interface Filters {
  benefitTypes: string[];
  veteranOnly: boolean;
  seniorOnly: boolean;
  disabilityPreferred: boolean;
  currentlyHomeless: boolean;
  maxIncome: string;     // numeric string or "" for no limit
  householdSize: string; // numeric string or "" for no limit
}

// Baseline filters — also used when the user clicks "home" to reset.
const DEFAULT_FILTERS: Filters = {
  benefitTypes: [],
  veteranOnly: false,
  seniorOnly: false,
  disabilityPreferred: false,
  currentlyHomeless: false,
  maxIncome: "",
  householdSize: "",
};

export default function App() {
  const { user } = useAuth(); // currently signed-in Firebase user (or null)

  // ── Core data state ──────────────────────────────────────────────────────
  const [policies, setPolicies] = useState<Policy[]>([]);   // deduplicated programs from API
  const [loading, setLoading] = useState(true);              // show spinner while fetching
  const [searchQuery, setSearchQuery] = useState("");        // text box value
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null); // modal target
  const [isModalOpen, setIsModalOpen] = useState(false);

  // ── UI state ─────────────────────────────────────────────────────────────
  const [bannerPassed, setBannerPassed] = useState(false);  // true once the hero banner is scrolled past
  const [filtersOpen, setFiltersOpen] = useState(false);    // filter dropdown visibility
  const [showSaved, setShowSaved] = useState(false);         // "Saved" view toggle in header
  const [sortBy, setSortBy] = useState("relevance");         // current sort selection
  const [toast, setToast] = useState<string | null>(null);  // ephemeral confirmation message

  // ── Per-user data ─────────────────────────────────────────────────────────
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());       // bookmark IDs
  const [subscribedIds, setSubscribedIds] = useState<Set<string>>(new Set()); // alert IDs

  const bannerRef = useRef<HTMLDivElement>(null); // ref to the hero image div for scroll detection

  // ── Load per-user data on sign-in ──────────────────────────────────────────
  // Fetch the list of policy IDs this user has saved.
  // Cleared immediately on sign-out so stale data isn't shown between sessions.
  useEffect(() => {
    if (!user) { setSavedIds(new Set()); return; }
    user.getIdToken().then((token) =>
      fetch("/api/saves", { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.json())
        .then((ids: string[]) => setSavedIds(new Set(ids)))
        .catch(() => {})
    );
  }, [user]);

  // Fetch the list of policy IDs this user has subscribed to for email alerts.
  useEffect(() => {
    if (!user) { setSubscribedIds(new Set()); return; }
    user.getIdToken().then((token) =>
      fetch("/api/subscriptions", { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.json())
        .then((ids: string[]) => setSubscribedIds(new Set(ids)))
        .catch(() => {})
    );
  }, [user]);

  const handleSave = async (policyId: string) => {
    if (!user) return;
    const token = await user.getIdToken();
    const isSaved = savedIds.has(policyId);
    const method = isSaved ? "DELETE" : "POST";
    const url = isSaved ? `/api/saves/${policyId}` : "/api/saves";
    const body = isSaved ? undefined : JSON.stringify({ policy_id: policyId });
    await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body,
    });
    setSavedIds((prev) => {
      const next = new Set(prev);
      isSaved ? next.delete(policyId) : next.add(policyId);
      return next;
    });
    if (!isSaved) setToast("Policy saved to your account.");
  };

  const handleSubscribe = async (policyId: string) => {
    if (!user) return;
    const token = await user.getIdToken();
    const isSubscribed = subscribedIds.has(policyId);
    const method = isSubscribed ? "DELETE" : "POST";
    const url = isSubscribed ? `/api/subscriptions/${policyId}` : "/api/subscriptions";
    const body = isSubscribed ? undefined : JSON.stringify({ policy_id: policyId });
    await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body,
    });
    setSubscribedIds((prev) => {
      const next = new Set(prev);
      isSubscribed ? next.delete(policyId) : next.add(policyId);
      return next;
    });
    if (!isSubscribed) setToast("You will receive email notifications when a change is made.");
  };

  useEffect(() => {
    const onScroll = () => {
      if (bannerRef.current) {
        setBannerPassed(window.scrollY >= bannerRef.current.offsetTop + bannerRef.current.offsetHeight);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest(".search-filter-wrapper")) {
        setFiltersOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // ── Backend fetch ──────────────────────────────────────────────────────────
  // Re-fetch whenever the user changes any filter.  Text search and sorting are
  // done client-side (see filteredPolicies below) so they don't trigger a fetch.
  useEffect(() => {
    const params = new URLSearchParams();
    filters.benefitTypes.forEach((t) => params.append("benefit_type", t));
    if (filters.veteranOnly) params.set("veteran_only", "true");
    if (filters.seniorOnly) params.set("senior_only", "true");
    if (filters.disabilityPreferred) params.set("disability_preferred", "true");
    if (filters.currentlyHomeless) params.set("currently_homeless_only", "true");
    if (filters.maxIncome) params.set("max_income", filters.maxIncome);
    if (filters.householdSize) params.set("household_size", filters.householdSize);

    setLoading(true);
    fetch(`/api/policies?${params}`)
      .then((r) => r.json())
      .then((data: Policy[]) => {
        // ── Client-side dedup ──────────────────────────────────────────────
        // The backend already deduplicates, but this second pass catches any
        // near-duplicates that slipped through (e.g. slightly different names
        // scraped from separate meeting years).
        //
        // Algorithm: for each policy, extract "significant words" (strip stop-
        // words and punctuation), then check if ≥85 % of the shorter title's
        // words appear in any already-accepted title.  If so, it's a duplicate
        // and we keep only the most-recently-dated one (sort descending first).
        const STOPWORDS = new Set(["of","the","a","an","for","and","or","to","in","at","by","from","with","is","its","are","on","as","be"]);
        const sigWords = (t: string) => new Set(
          t.toLowerCase().replace(/[^\w\s]/g, " ").split(/\s+/).filter(w => w.length > 2 && !STOPWORDS.has(w))
        );
        const isDup = (a: Set<string>, b: Set<string>) => {
          if (!a.size || !b.size) return false;
          const [short, long] = a.size <= b.size ? [a, b] : [b, a];
          // Very short names (< 3 sig words) require exact match to avoid false positives.
          if (short.size < 3) return a.size === b.size && [...a].every(w => b.has(w));
          return [...short].filter(w => long.has(w)).length / short.size >= 0.85;
        };
        // Sort most-recent first so the representative we keep is always the newest.
        const sorted = [...data].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
        const groups: Policy[] = [];
        const groupSets: Set<string>[] = [];
        for (const p of sorted) {
          const ws = sigWords(p.title);
          if (!groupSets.some(gs => isDup(ws, gs))) { groups.push(p); groupSets.push(ws); }
        }
        setPolicies(groups);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [filters]);

  // ── Client-side text search + sort ────────────────────────────────────────
  // Runs entirely in the browser — no additional API calls needed.
  // Searches title, summary, and tags.  Sort order is applied after filtering.
  const filteredPolicies = useMemo(() => {
    let result = policies;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          p.summary.toLowerCase().includes(q) ||
          p.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    return [...result].sort((a, b) => {
      switch (sortBy) {
        case "alpha-asc":
          return a.title.localeCompare(b.title);
        case "alpha-desc":
          return b.title.localeCompare(a.title);
        case "date-desc":
          return (b.date || "").localeCompare(a.date || "");
        case "date-asc":
          return (a.date || "").localeCompare(b.date || "");
        case "funding-desc": {
          const aAmt = parseFloat((a.funding_amount || "0").replace(/[^0-9.]/g, "")) || 0;
          const bAmt = parseFloat((b.funding_amount || "0").replace(/[^0-9.]/g, "")) || 0;
          return bAmt - aAmt;
        }
        default: // "relevance" — targeted programs first
          return ((b.targeted_labels?.length ?? 0) > 0 ? 1 : 0) -
                 ((a.targeted_labels?.length ?? 0) > 0 ? 1 : 0);
      }
    });
  }, [policies, searchQuery, sortBy]);

  const displayedPolicies = showSaved ? filteredPolicies.filter(p => savedIds.has(p.id)) : filteredPolicies;

  const anyProfileActive = filters.veteranOnly || filters.seniorOnly || filters.disabilityPreferred || filters.currentlyHomeless;

  const targetedPolicies = anyProfileActive ? displayedPolicies.filter(p => (p.targeted_labels?.length ?? 0) > 0) : [];
  const otherPolicies    = anyProfileActive ? displayedPolicies.filter(p => (p.targeted_labels?.length ?? 0) === 0) : displayedPolicies;

  const profileLabel = [
    filters.veteranOnly         && "Veterans",
    filters.seniorOnly          && "Seniors (65+)",
    filters.disabilityPreferred && "People with Disabilities",
    filters.currentlyHomeless   && "People Experiencing Homelessness",
  ].filter(Boolean).join(" & ");

  const featuredPolicy = filteredPolicies[0];

  const filterDropdown = (
    <div className="absolute top-full left-0 right-0 mt-2 z-50 rounded-2xl bg-white shadow-xl border border-gray-100">
      {/* Row 1: checkboxes */}
      <div className="flex items-center gap-6 px-6 pt-4 pb-3">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest shrink-0">I am a...</span>
        {[
          { key: "veteranOnly",         label: "Veteran" },
          { key: "seniorOnly",          label: "Senior (65+)" },
          { key: "disabilityPreferred", label: "Person with Disability" },
          { key: "currentlyHomeless",   label: "Currently Homeless" },
        ].map(({ key, label }) => {
          const checked = filters[key as keyof Filters] as boolean;
          return (
            <label key={key} className="flex items-center gap-1.5 cursor-pointer group">
              <input
                type="checkbox"
                checked={checked}
                onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
                className="w-4 h-4 accent-blue-500"
              />
              <span className={`text-sm font-medium transition-colors ${checked ? "text-blue-600" : "text-gray-600 group-hover:text-gray-900"}`}>
                {label}
              </span>
            </label>
          );
        })}
      </div>
      {/* Row 2: selects */}
      <div className="flex items-center gap-4 px-6 pb-4 pt-2 border-t border-gray-100">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest shrink-0">Sort by...</span>
        <div className="relative flex-1">
          <select
            value={filters.maxIncome}
            onChange={(e) => setFilters({ ...filters, maxIncome: e.target.value })}
            className="w-full px-3 py-1.5 pr-8 text-sm font-medium rounded-lg border border-gray-200 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 appearance-none cursor-pointer"
          >
            <option value="">Income</option>
            <option value="20000">Under $20k</option>
            <option value="35000">$20k – $35k</option>
            <option value="50000">$35k – $50k</option>
            <option value="80000">$50k – $80k</option>
            <option value="120000">$80k – $120k</option>
            <option value="999999">Over $120k</option>
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-900 pointer-events-none" />
        </div>
        <div className="relative flex-1">
          <select
            value={filters.householdSize}
            onChange={(e) => setFilters({ ...filters, householdSize: e.target.value })}
            className="w-full px-3 py-1.5 pr-8 text-sm font-medium rounded-lg border border-gray-200 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 appearance-none cursor-pointer"
          >
            <option value="">Household Size</option>
            <option value="1">1 person</option>
            <option value="2">2 people</option>
            <option value="3">3 people</option>
            <option value="4">4 people</option>
            <option value="5">5 people</option>
            <option value="6">6+ people</option>
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-900 pointer-events-none" />
        </div>
        <div className="relative flex-1">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="w-full px-3 py-1.5 pr-8 text-sm font-medium rounded-lg border border-gray-200 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 appearance-none cursor-pointer"
          >
            <option value="relevance">Sort: Relevance</option>
            <option value="date-desc">Sort: Most Recent</option>
            <option value="date-asc">Sort: Oldest First</option>
            <option value="alpha-asc">Sort: A → Z</option>
            <option value="alpha-desc">Sort: Z → A</option>
            <option value="funding-desc">Sort: Highest Funding</option>
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-900 pointer-events-none" />
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
          <button
            className="flex items-center gap-3 shrink-0 group"
            onClick={() => { setSearchQuery(""); setFilters(DEFAULT_FILTERS); setSortBy("relevance"); setShowSaved(false); setFiltersOpen(false); }}
          >
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center group-hover:bg-blue-700 transition-colors">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div className="text-left">
              <h1 className="text-xl font-bold text-gray-900">GovPolicy Hub</h1>
              <p className="text-xs text-gray-500">San Jose Housing Policy Center</p>
            </div>
          </button>
          {bannerPassed && (
            <div className="search-filter-wrapper flex-1 relative">
              <SearchBar value={searchQuery} onChange={setSearchQuery} onFocus={() => setFiltersOpen(true)} />
              {filtersOpen && filterDropdown}
            </div>
          )}
          <div className="ml-auto flex items-center gap-3 shrink-0">
            <UserMenu />
            {user && (
              <button
                onClick={() => setShowSaved((s) => !s)}
                title={showSaved ? "Show all policies" : "Show saved policies"}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors border ${
                  showSaved
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-200 hover:border-blue-400 hover:text-blue-600"
                }`}
              >
                <Bookmark className="w-4 h-4" />
                Saved{showSaved ? "" : savedIds.size > 0 ? ` (${savedIds.size})` : ""}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Banner */}
      <div ref={bannerRef} className="relative w-full">
        <img
          src="/banner.jpg"
          alt="GovPolicy Hub banner"
          className="w-full object-cover"
          style={{ maxHeight: "340px", minHeight: "240px" }}
        />
        <div className="absolute inset-0 bg-black/45" />
        <div className="absolute inset-0 flex flex-col items-center justify-center px-6 gap-4">
          <h2 className="text-8xl font-bold text-white drop-shadow-lg tracking-tight">City of San Jose</h2>
          <div className="search-filter-wrapper relative w-full max-w-2xl">
            <SearchBar value={searchQuery} onChange={setSearchQuery} onFocus={() => setFiltersOpen(true)} />
            {filtersOpen && filterDropdown}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <p className="text-gray-500 text-lg">Loading policies...</p>
          </div>
        ) : (
          <>
            {/* Featured Policy */}
            {featuredPolicy && !searchQuery && (
              <div className="mb-8">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-bold text-gray-900">Featured Policy</h2>
                </div>
                <PolicyCard
                  policy={featuredPolicy}
                  variant="featured"
                  onClick={() => { setSelectedPolicy(featuredPolicy); setIsModalOpen(true); }}
                />
              </div>
            )}

            {/* Results Header */}
            <div className="mb-6">
              <h2 className="text-xl font-bold text-gray-900">
                {showSaved ? "Saved Policies" : searchQuery ? `Search Results (${displayedPolicies.length})` : "All Policies"}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                {displayedPolicies.length} {displayedPolicies.length === 1 ? "policy" : "policies"} found
              </p>
            </div>

            {/* Policy Grid — split into targeted + other when profile filters are active */}
            {displayedPolicies.length > 0 ? (
              <>
                {anyProfileActive && targetedPolicies.length > 0 && (
                  <div className="mb-10">
                    <div className="flex items-center gap-3 mb-4">
                      <span className="px-3 py-1 bg-blue-600 text-white text-xs font-bold rounded-full uppercase tracking-wide">
                        For {profileLabel}
                      </span>
                      <span className="text-sm text-gray-400">{targetedPolicies.length} tailored {targetedPolicies.length === 1 ? "program" : "programs"}</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {targetedPolicies.map((policy) => (
                        <PolicyCard
                          key={policy.id}
                          policy={policy}
                          variant="default"
                          onClick={() => { setSelectedPolicy(policy); setIsModalOpen(true); }}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {anyProfileActive && otherPolicies.length > 0 && (
                  <div className="mb-4">
                    <div className="flex items-center gap-3 mb-4">
                      <span className="px-3 py-1 bg-gray-200 text-gray-600 text-xs font-bold rounded-full uppercase tracking-wide">
                        Also Eligible
                      </span>
                      <span className="text-sm text-gray-400">{otherPolicies.length} additional {otherPolicies.length === 1 ? "program" : "programs"}</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {otherPolicies.map((policy) => (
                        <PolicyCard
                          key={policy.id}
                          policy={policy}
                          variant="default"
                          onClick={() => { setSelectedPolicy(policy); setIsModalOpen(true); }}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {!anyProfileActive && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {displayedPolicies.map((policy, index) => (
                      <PolicyCard
                        key={policy.id}
                        policy={policy}
                        variant={index % 7 === 0 && index !== 0 ? "compact" : "default"}
                        onClick={() => { setSelectedPolicy(policy); setIsModalOpen(true); }}
                      />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                  <AlertCircle className="w-10 h-10 text-gray-400" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No Policies Found</h3>
                <p className="text-gray-500 max-w-md">
                  {showSaved
                    ? "You haven't saved any policies yet. Click the bookmark icon on a policy to save it."
                    : searchQuery
                    ? `No policies match "${searchQuery}". Try different keywords.`
                    : "No policies match your current filters. Try adjusting them."}
                </p>
              </div>
            )}
          </>
        )}
      </main>

      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-8 text-center text-sm text-gray-500">
          © 2026 GovPolicy Hub · Data sourced from San Jose City Council meeting minutes
        </div>
      </footer>

      <PolicyDetailModal
        policy={selectedPolicy}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        isSaved={selectedPolicy ? savedIds.has(selectedPolicy.id) : false}
        onSave={selectedPolicy ? () => handleSave(selectedPolicy.id) : undefined}
        isLoggedIn={!!user}
        isSubscribed={selectedPolicy ? subscribedIds.has(selectedPolicy.id) : false}
        onSubscribe={selectedPolicy ? () => handleSubscribe(selectedPolicy.id) : undefined}
      />

      {toast && <Toast key={toast} message={toast} onDone={() => setToast(null)} />}
    </div>
  );
}
