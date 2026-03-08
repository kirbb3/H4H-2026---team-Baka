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
  );
}
