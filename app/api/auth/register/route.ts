import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import DOMPurify from "isomorphic-dompurify";

import { hashPassword } from "@/lib/auth";
import { createUser, findUserByEmail } from "@/lib/db";
import { rateLimit } from "@/lib/rate-limit";

// Step 1: Define a Zod schema with strict constraints.
// `.strict()` rejects unknown keys — prevents mass-assignment attacks.
const registerSchema = z
  .object({
    username: z
      .string({
        required_error: "Username is required",
        invalid_type_error: "Username must be a string",
      })
      .trim()
      .min(3, "Username must be at least 3 characters")
      .max(32, "Username must not exceed 32 characters")
      .regex(
        /^[a-zA-Z0-9_-]+$/,
        "Username may only contain letters, numbers, hyphens, and underscores"
      ),

    // .email() validates RFC 5322 format and checks for a TLD.
    email: z
      .string({ required_error: "Email is required" })
      .trim()
      .toLowerCase() // Normalize case before further validation
      .email("Invalid email address")
      .max(254, "Email must not exceed 254 characters"), // RFC 5321 limit

    password: z
      .string({ required_error: "Password is required" })
      .min(12, "Password must be at least 12 characters")
      .max(128, "Password must not exceed 128 characters")
      // Require at least one lowercase, one uppercase, one digit, one special char.
      .regex(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d\s]).{12,}$/,
        "Password must contain uppercase, lowercase, digit, and special character"
      ),
  })
  .strict();

// Step 2: Derive the TypeScript type from the schema (single source of truth).
type RegisterInput = z.infer<typeof registerSchema>;

/**
 * Step 3: Sanitize string values after validation.
 *
 * Why sanitize after validation?  Validation ensures the data structure is
 * correct; sanitization removes potentially dangerous content that is
 * structurally valid (e.g. <script> tags in a username).
 *
 * DOMPurify is used with only ALLOWED_TAGS: []  to strip ALL HTML.
 * This prevents both XSS (stored/reflected) and HTML injection.
 */
function sanitize(input: RegisterInput): RegisterInput {
  return {
    username: DOMPurify.sanitize(input.username, { ALLOWED_TAGS: [] }),
    email: DOMPurify.sanitize(input.email, { ALLOWED_TAGS: [] }),
    // Passwords are hashed, not rendered, so HTML sanitization isn't needed
    // here. They're handled securely below by bcrypt.
    password: input.password,
  };
}

/**
 * POST /api/auth/register
 *
 * Best practices demonstrated:
 *  - Schema-first validation with Zod (fail closed — reject unknown fields).
 *  - Input sanitization via DOMPurify to strip HTML/XSS vectors.
 *  - Rate limiting to prevent brute-force and enumeration.
 *  - Password hashing with bcrypt (never store plaintext).
 *  - Generic error messages (don't leak whether email already exists).
 *  - Early returns for invalid/malformed payloads.
 *  - Content-Type enforcement (application/json only).
 */
export async function POST(request: NextRequest) {
  // Step 4: Rate limit by IP to prevent abuse.
  const ip = request.headers.get("x-forwarded-for") ?? "unknown";
  const { success } = await rateLimit(ip, { limit: 5, window: 60 });
  if (!success) {
    return NextResponse.json(
      { error: "Too many requests. Please try again later." },
      { status: 429 }
    );
  }

  // Step 5: Enforce Content-Type to reject non-JSON payloads.
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return NextResponse.json(
      { error: "Content-Type must be application/json" },
      { status: 415 }
    );
  }

  // Step 6: Parse the raw JSON body. Wrapping in try/catch protects
  // against malformed JSON that would otherwise crash the handler.
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  // Step 7: Validate with Zod.  .safeParse() returns a result object
  // instead of throwing, giving us structured error access.
  const parsed = registerSchema.safeParse(body);
  if (!parsed.success) {
    // Zod issues are flattened into { field: [message, ...], ... }.
    // We never expose raw stack traces or internal error objects.
    return NextResponse.json(
      { error: "Validation failed", fields: parsed.error.flatten().fieldErrors },
      { status: 422 }
    );
  }

  // Step 8: Sanitize the validated data.
  const clean = sanitize(parsed.data);

  // Step 9: Check for existing user (after validation & sanitization).
  // Use a generic error to prevent email enumeration.
  const existing = await findUserByEmail(clean.email);
  if (existing) {
    return NextResponse.json(
      { error: "Registration failed. Please check your input." },
      { status: 409 }
    );
  }

  // Step 10: Hash the password with bcrypt (salt rounds = 12).
  // Never log, store, or return the plaintext password.
  const passwordHash = await hashPassword(clean.password);

  // Step 11: Persist to the database. Only the sanitized & hashed data
  // is stored — original input is discarded.
  const user = await createUser({
    username: clean.username,
    email: clean.email,
    passwordHash,
  });

  // Step 12: Return a minimal response. Never include the password hash
  // or other internal fields in API responses.
  return NextResponse.json(
    {
      id: user.id,
      username: user.username,
      email: user.email,
      createdAt: user.createdAt,
    },
    { status: 201 }
  );
}
