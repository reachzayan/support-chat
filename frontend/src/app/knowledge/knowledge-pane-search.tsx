/* oxlint-disable react-perf/jsx-no-new-function-as-prop -- Controlled input handlers use current field values. */

import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"

export const PaneSearch = ({
  id,
  label,
  value,
  onQuery,
  placeholder,
}: {
  id: string
  label: string
  value: string
  onQuery: (value: string) => void
  placeholder: string
}) => (
  <label htmlFor={id} className="relative block">
    <span className="sr-only">{label}</span>
    <Search aria-hidden="true" className="text-mute absolute top-2.5 left-3 size-3.5" />
    <Input
      id={id}
      type="search"
      aria-label={label}
      value={value}
      onChange={(event) => onQuery(event.target.value)}
      placeholder={placeholder}
      className="border-line bg-ice-2/60 text-ink placeholder:text-mute h-9 rounded-[9px] border pr-3 pl-9 text-xs"
    />
  </label>
)
