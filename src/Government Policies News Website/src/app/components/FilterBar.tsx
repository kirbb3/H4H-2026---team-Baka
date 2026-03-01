interface Filters {
  benefitTypes: string[];
  veteranOnly: boolean;
  seniorOnly: boolean;
  disabilityPreferred: boolean;
  currentlyHomeless: boolean;
  maxIncome: string;
  householdSize: string;
}

interface FilterBarProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

const BENEFIT_TYPES = [
  { id: "rent",        label: "Rental Assistance" },
  { id: "emergency",   label: "Emergency Housing" },
  { id: "policy",      label: "Policy" },
  { id: "homebuyer",   label: "Homebuyer" },
  { id: "development", label: "Development" },
  { id: "other",       label: "Other" },
];

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const hasActiveFilters =
    filters.benefitTypes.length > 0 ||
    filters.veteranOnly ||
    filters.seniorOnly ||
    filters.disabilityPreferred ||
    filters.currentlyHomeless ||
    filters.maxIncome !== "" ||
    filters.householdSize !== "";

  const toggleBenefitType = (id: string) => {
    const updated = filters.benefitTypes.includes(id)
      ? filters.benefitTypes.filter((t) => t !== id)
      : [...filters.benefitTypes, id];
    onChange({ ...filters, benefitTypes: updated });
  };

  const clearAll = () => {
    onChange({
      benefitTypes: [],
      veteranOnly: false,
      seniorOnly: false,
      disabilityPreferred: false,
      currentlyHomeless: false,
      maxIncome: "",
      householdSize: "",
    });
  };

  return (
    <div className="space-y-4">
      {/* Benefit type pills */}
      <div className="flex flex-wrap gap-2">
        {BENEFIT_TYPES.map((type) => {
          const active = filters.benefitTypes.includes(type.id);
          return (
            <button
              key={type.id}
              onClick={() => toggleBenefitType(type.id)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                active
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600"
              }`}
            >
              {type.label}
            </button>
          );
        })}
        {hasActiveFilters && (
          <button
            onClick={clearAll}
            className="px-4 py-1.5 rounded-full text-sm font-medium border border-red-300 text-red-500 hover:bg-red-50 transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Profile filters */}
      <div className="bg-gray-50 rounded-xl p-4 flex flex-wrap gap-6 items-end">
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">I am a...</p>
          <div className="flex flex-wrap gap-3">
            {[
              { key: "veteranOnly",        label: "Veteran" },
              { key: "seniorOnly",         label: "Senior (65+)" },
              { key: "disabilityPreferred", label: "Person with Disability" },
              { key: "currentlyHomeless",  label: "Currently Homeless" },
            ].map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters[key as keyof Filters] as boolean}
                  onChange={(e) => onChange({ ...filters, [key]: e.target.checked })}
                  className="w-4 h-4 accent-blue-600"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex gap-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Annual Income ($)
            </label>
            <input
              type="number"
              placeholder="e.g. 50000"
              value={filters.maxIncome}
              onChange={(e) => onChange({ ...filters, maxIncome: e.target.value })}
              className="w-36 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Household Size
            </label>
            <input
              type="number"
              placeholder="e.g. 3"
              min={1}
              value={filters.householdSize}
              onChange={(e) => onChange({ ...filters, householdSize: e.target.value })}
              className="w-28 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
