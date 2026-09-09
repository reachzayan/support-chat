import { Schema, SchemaTransformation } from "effect"

const StaffEmail = Schema.String.pipe(
  Schema.decode(SchemaTransformation.trim()),
  Schema.decode(SchemaTransformation.toLowerCase()),
  Schema.check(Schema.isNonEmpty(), Schema.isPattern(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)),
)

export const parseStaffEmail = Schema.decodeUnknownEffect(StaffEmail)
