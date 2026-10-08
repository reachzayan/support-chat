import { render, screen } from "@testing-library/react"
import { expect, test } from "vitest"

import NotFound from "./not-found"

test("the branded not-found page offers a way back to the inbox and sign-in", () => {
  render(<NotFound />)
  expect(
    screen.getByRole("heading", { level: 1, name: "This page could not be found" }),
  ).toBeVisible()
  expect(screen.getByRole("link", { name: "Go to the inbox" })).toHaveAttribute(
    "href",
    "/admin/inbox",
  )
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login")
})
