"use client"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"

type Candidate = {
  unit_id: string
  canonical_question: string | null
  heading: string | null
  rejection_reason: string | null
}

type CandidateEvidenceListProps = {
  candidates: Candidate[]
}

export const CandidateEvidenceList = ({ candidates }: CandidateEvidenceListProps) => {
  if (candidates.length === 0) {
    return <p className="text-mute text-xs">No candidate evidence recorded.</p>
  }
  return (
    <Collapsible defaultOpen={false}>
      <CollapsibleTrigger aria-label="Candidate evidence">
        <span>Candidate evidence ({candidates.length})</span>
        <span className="text-mute text-xs font-normal">Show</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ScrollArea className="max-h-40">
          <ul className="flex flex-col gap-2">
            {candidates.map((item) => {
              const title = item.canonical_question?.trim() || item.heading?.trim() || item.unit_id
              return (
                <li
                  key={item.unit_id}
                  className="border-line bg-ice rounded-[8px] border px-3 py-2"
                >
                  <p className="text-ink text-xs leading-5 font-semibold">{title}</p>
                  {item.rejection_reason ? (
                    <p className="text-mute mt-1 font-mono text-[11px]">{item.rejection_reason}</p>
                  ) : null}
                </li>
              )
            })}
          </ul>
        </ScrollArea>
      </CollapsibleContent>
    </Collapsible>
  )
}
