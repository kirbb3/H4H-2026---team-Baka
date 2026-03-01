import { useState, useMemo, useEffect } from "react";
import { FileText, TrendingUp, AlertCircle } from "lucide-react";
import { PolicyCard } from "./components/PolicyCard";
import { SearchBar } from "./components/SearchBar";
import { FilterBar } from "./components/FilterBar";
import { PolicyDetailModal } from "./components/PolicyDetailModal";

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
  benefit_type?: string;
  targeted_labels?: string[];
}

interface Filters {
  benefitTypes: string[];
  veteranOnly: boolean;
  seniorOnly: boolean;
  disabilityPreferred: boolean;
  currentlyHomeless: boolean;
  maxIncome: string;
  householdSize: string;
}

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
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Fetch from backend whenever filters change
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
      .then((data) => { setPolicies(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filters]);

  // Client-side text search + sort targeted programs to the top
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
    // Targeted programs (matched to the user's profile) float to the top
    return [...result].sort((a, b) => {
      const aTargeted = (a.targeted_labels?.length ?? 0) > 0 ? 1 : 0;
      const bTargeted = (b.targeted_labels?.length ?? 0) > 0 ? 1 : 0;
      return bTargeted - aTargeted;
    });
  }, [policies, searchQuery]);

  const stats = useMemo(() => ({
    total: policies.length,
    active: policies.filter((p) => p.status === "Active").length,
  }), [policies]);

  const featuredPolicy = filteredPolicies[0];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
                <FileText className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">GovPolicy Hub</h1>
                <p className="text-sm text-gray-500">San Jose Housing Policy Center</p>
              </div>
            </div>
            <div className="hidden md:flex gap-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
                <div className="text-xs text-gray-500">Total Policies</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{stats.active}</div>
                <div className="text-xs text-gray-500">Active</div>
              </div>
            </div>
          </div>

          <FilterBar filters={filters} onChange={setFilters} />
        </div>
      </header>

      {/* Banner with integrated search + profile filters */}
      <div className="relative w-full">
        <img
          src="/banner.jpg"
          alt="GovPolicy Hub banner"
          className="w-full object-cover"
          style={{ maxHeight: "340px", minHeight: "240px" }}
        />
        <div className="absolute inset-0 bg-black/45" />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 px-6">
          <SearchBar value={searchQuery} onChange={setSearchQuery} />
          <div className="flex flex-wrap gap-x-8 gap-y-3 items-center justify-center bg-black/30 backdrop-blur-sm rounded-2xl px-8 py-4">
            <div>
              <p className="text-xs font-bold text-white uppercase tracking-widest mb-2">I am a...</p>
              <div className="flex flex-wrap gap-4">
                {[
                  { key: "veteranOnly",         label: "Veteran" },
                  { key: "seniorOnly",          label: "Senior (65+)" },
                  { key: "disabilityPreferred", label: "Person with Disability" },
                  { key: "currentlyHomeless",   label: "Currently Homeless" },
                ].map(({ key, label }) => {
                  const checked = filters[key as keyof Filters] as boolean;
                  return (
                    <label key={key} className="flex items-center gap-2 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
                        className="w-5 h-5 accent-blue-400"
                      />
                      <span className={`text-base font-semibold transition-colors ${checked ? "text-white" : "text-white/90 group-hover:text-white"}`}>
                        {label}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="flex gap-5">
              <div>
                <label className="block text-xs font-bold text-white uppercase tracking-widest mb-1.5">
                  Annual Income
                </label>
                <select
                  value={filters.maxIncome}
                  onChange={(e) => setFilters({ ...filters, maxIncome: e.target.value })}
                  className="w-48 px-3 py-2 text-base font-medium border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white text-gray-800"
                >
                  <option value="" className="text-gray-900 bg-white">Any income</option>
                  <option value="20000" className="text-gray-900 bg-white">Under $20,000</option>
                  <option value="35000" className="text-gray-900 bg-white">$20,000 – $35,000</option>
                  <option value="50000" className="text-gray-900 bg-white">$35,000 – $50,000</option>
                  <option value="80000" className="text-gray-900 bg-white">$50,000 – $80,000</option>
                  <option value="120000" className="text-gray-900 bg-white">$80,000 – $120,000</option>
                  <option value="999999" className="text-gray-900 bg-white">Over $120,000</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-white uppercase tracking-widest mb-1.5">
                  Household Size
                </label>
                <select
                  value={filters.householdSize}
                  onChange={(e) => setFilters({ ...filters, householdSize: e.target.value })}
                  className="w-48 px-3 py-2 text-base font-medium border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white text-gray-800"
                >
                  <option value="" className="text-gray-900 bg-white">Any size</option>
                  <option value="1" className="text-gray-900 bg-white">1 person</option>
                  <option value="2" className="text-gray-900 bg-white">2 people</option>
                  <option value="3" className="text-gray-900 bg-white">3 people</option>
                  <option value="4" className="text-gray-900 bg-white">4 people</option>
                  <option value="5" className="text-gray-900 bg-white">5 people</option>
                  <option value="6" className="text-gray-900 bg-white">6+ people</option>
                </select>
              </div>
            </div>
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
                {searchQuery ? `Search Results (${filteredPolicies.length})` : "All Policies"}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                {filteredPolicies.length} {filteredPolicies.length === 1 ? "policy" : "policies"} found
              </p>
            </div>

            {/* Policy Grid */}
            {filteredPolicies.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredPolicies.map((policy, index) => (
                  <PolicyCard
                    key={policy.id}
                    policy={policy}
                    variant={index % 7 === 0 && index !== 0 ? "compact" : "default"}
                    onClick={() => { setSelectedPolicy(policy); setIsModalOpen(true); }}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                  <AlertCircle className="w-10 h-10 text-gray-400" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No Policies Found</h3>
                <p className="text-gray-500 max-w-md">
                  {searchQuery
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
      />
    </div>
  );
}
