"use client"

/* oxlint-disable react-perf/jsx-no-new-object-as-prop -- motion enter props need a static variant object per panel */

import { motion, useReducedMotion } from "motion/react"
import type { ReactNode } from "react"

import { BrandMark } from "@/components/brand-mark"
import { ThemeToggle } from "@/components/theme-toggle"

const EASE = [0.22, 1, 0.36, 1] as const
const ENTER = { duration: 0.2, ease: EASE }
const STILL = { duration: 0 }
const hidden = { opacity: 0, y: 10 }
const shown = { opacity: 1, y: 0 }

export const LoginStage = ({ children }: { children: ReactNode }) => {
  const reducedMotion = useReducedMotion()

  return (
    <div className="bg-ice flex min-h-dvh flex-col lg:flex-row">
      <CaseRoom reducedMotion={Boolean(reducedMotion)} />
      <section className="relative flex flex-1 items-center justify-center px-5 py-14 sm:px-8 lg:justify-start lg:px-16 xl:px-24">
        <div className="absolute top-5 right-5 hidden lg:block">
          <ThemeToggle />
        </div>
        <motion.div
          initial={reducedMotion ? false : hidden}
          animate={shown}
          transition={reducedMotion ? STILL : { ...ENTER, delay: 0.08 }}
          className="w-full max-w-[26rem]"
        >
          {children}
        </motion.div>
      </section>
    </div>
  )
}

const CaseRoom = ({ reducedMotion }: { reducedMotion: boolean }) => (
  <aside className="bg-navy-deep relative isolate flex min-h-[18rem] overflow-hidden text-white lg:h-dvh lg:min-h-dvh lg:w-[46%]">
    <div className="login-rules pointer-events-none absolute inset-0 opacity-70" />
    <div className="login-glow pointer-events-none absolute -top-24 -left-16 size-[22rem] rounded-full bg-[radial-gradient(circle,rgb(36_86_160/0.28),transparent_68%)]" />
    <div className="login-glow pointer-events-none absolute right-[-6rem] bottom-[-4rem] size-[18rem] rounded-full bg-[radial-gradient(circle,rgb(196_85_22/0.18),transparent_70%)]" />
    <div className="bg-ember absolute top-0 right-0 hidden h-full w-1.5 rounded-l-full lg:block" />
    <div className="relative z-10 flex w-full flex-col justify-between px-7 py-6 sm:px-10 lg:px-14 lg:py-12">
      <CaseHeader />
      <motion.div
        initial={reducedMotion ? false : hidden}
        animate={shown}
        transition={reducedMotion ? STILL : { ...ENTER, delay: 0.04 }}
        className="flex flex-1 flex-col justify-end gap-8 py-8 lg:justify-center lg:gap-12 lg:py-0"
      >
        <CaseCopy />
      </motion.div>
      <p className="hidden font-mono text-[10px] tracking-[0.18em] text-white/35 uppercase lg:block">
        Invite only
      </p>
    </div>
  </aside>
)

const CaseHeader = () => (
  <div className="flex items-start justify-between gap-4">
    <div className="flex items-center gap-3">
      <BrandMark size={36} className="size-9" />
      <div>
        <p className="text-[11px] font-semibold tracking-[0.2em] text-white/70 uppercase">
          SupportChat
        </p>
        <p className="mt-1 text-sm font-medium tracking-wide text-white/85">Screening operations</p>
      </div>
    </div>
    <div className="lg:hidden">
      <ThemeToggle compact />
    </div>
  </div>
)

const CaseCopy = () => (
  <div className="max-w-sm">
    <h2 className="heading text-[1.75rem] text-balance sm:text-4xl">The specialist desk.</h2>
    <p className="mt-4 text-sm leading-6 text-white/65">
      Invited operators join visitor chats. Transcripts stay on this site.
    </p>
  </div>
)
