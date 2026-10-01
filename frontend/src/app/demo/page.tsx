import { DemoWidgetEmbed } from "@/components/demo-widget-embed"

export default function DemoPage() {
  return (
    <main className="relative flex min-h-dvh items-center justify-center bg-[#F4F8FF] px-6 text-center text-[#0D1F3A]">
      <h1 className="heading max-w-lg text-2xl text-balance sm:text-3xl">
        This is a demo website for the Chatbot widget.
      </h1>
      <DemoWidgetEmbed />
    </main>
  )
}
