"use server";

export type ContactFormState = {
  status: "idle" | "success" | "error";
  errors?: {
    name?: string;
    email?: string;
    message?: string;
  };
};

export async function submitContact(
  _prev: ContactFormState,
  formData: FormData,
): Promise<ContactFormState> {
  const name = String(formData.get("name") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim();
  const company = String(formData.get("company") ?? "").trim();
  const interest = String(formData.get("interest") ?? "").trim();
  const message = String(formData.get("message") ?? "").trim();

  const errors: NonNullable<ContactFormState["errors"]> = {};
  if (!name) errors.name = "Enter your name.";
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (!message) errors.message = "Tell us a little about your project.";

  if (Object.keys(errors).length > 0) {
    return { status: "error", errors };
  }

  // ponytail: enquiries are logged server-side for now; wire this to an email
  // provider or CRM (e.g. Resend, HubSpot) once one is chosen.
  console.log("[contact enquiry]", {
    name,
    email,
    phone,
    company,
    interest,
    message,
  });

  return { status: "success" };
}
