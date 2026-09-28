import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type SelectOption = { value: string; label: string }

export const scopeOptions = (sites: { id: string; name: string }[]): SelectOption[] => [
  { value: "general", label: "General — all websites" },
  ...sites.map((site) => ({ value: site.id, label: site.name })),
]

export const statusOptions: SelectOption[] = [
  { value: "all", label: "All" },
  { value: "enabled", label: "Enabled" },
  { value: "disabled", label: "Disabled" },
]

export const CannedResponseSelect = ({
  value,
  onValueChange,
  items,
  id,
  label,
}: {
  value: string | null
  onValueChange: (value: string | null) => void
  items: SelectOption[]
  id?: string
  label?: string
}) => (
  <Select value={value} onValueChange={onValueChange} items={items}>
    <SelectTrigger
      id={id}
      aria-label={label}
      className="border-line bg-ice h-10 min-h-10 w-full rounded-[8px] data-[size=default]:h-10"
    >
      <SelectValue />
    </SelectTrigger>
    <SelectContent align="start" alignItemWithTrigger={false}>
      <SelectGroup>
        {items.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectGroup>
    </SelectContent>
  </Select>
)
