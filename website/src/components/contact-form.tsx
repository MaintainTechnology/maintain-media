"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { CheckCircle, PaperPlaneTilt } from "@phosphor-icons/react";
import { submitContact, type ContactFormState } from "@/app/contact/actions";

const initialState: ContactFormState = { status: "idle" };

const inputClasses =
  "w-full rounded-md border border-line bg-canvas/60 px-4 py-3 text-ink placeholder:text-mist focus:border-brand focus:outline-none";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="btn btn-primary w-full disabled:cursor-not-allowed disabled:opacity-70"
    >
      {pending ? (
        "Sending…"
      ) : (
        <>
          Send message
          <PaperPlaneTilt size={18} weight="bold" />
        </>
      )}
    </button>
  );
}

export function ContactForm() {
  const [state, formAction] = useActionState(submitContact, initialState);

  if (state.status === "success") {
    return (
      <div
        role="status"
        className="flex h-full min-h-[24rem] flex-col items-center justify-center rounded-lg border border-line bg-surface p-10 text-center"
      >
        <CheckCircle size={56} weight="duotone" className="text-brand" />
        <h3 className="mt-5 font-display text-2xl font-bold">
          Thanks, message received.
        </h3>
        <p className="mt-3 max-w-sm text-ink-2">
          We will come back to you within one business day with clear next
          steps.
        </p>
      </div>
    );
  }

  const errors = state.errors ?? {};

  return (
    <form
      action={formAction}
      noValidate
      className="rounded-lg border border-line bg-surface p-7 md:p-9"
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="name" className="mb-2 block text-sm font-semibold text-ink">
            Full name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            required
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? "name-error" : undefined}
            className={inputClasses}
          />
          {errors.name && (
            <p id="name-error" className="mt-2 text-sm text-brand-300">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="email" className="mb-2 block text-sm font-semibold text-ink">
            Work email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? "email-error" : undefined}
            className={inputClasses}
          />
          {errors.email && (
            <p id="email-error" className="mt-2 text-sm text-brand-300">
              {errors.email}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="phone" className="mb-2 block text-sm font-semibold text-ink">
            Phone <span className="font-normal text-mist">(optional)</span>
          </label>
          <input
            id="phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            className={inputClasses}
          />
        </div>
        <div>
          <label htmlFor="company" className="mb-2 block text-sm font-semibold text-ink">
            Company <span className="font-normal text-mist">(optional)</span>
          </label>
          <input
            id="company"
            name="company"
            type="text"
            autoComplete="organization"
            className={inputClasses}
          />
        </div>
      </div>

      <div className="mt-5">
        <label htmlFor="interest" className="mb-2 block text-sm font-semibold text-ink">
          What are you interested in?
        </label>
        <select id="interest" name="interest" className={inputClasses} defaultValue="">
          <option value="" disabled>
            Select an option
          </option>
          <option>Brand &amp; Creative</option>
          <option>Digital &amp; Performance</option>
          <option>Content &amp; Social</option>
          <option>Web &amp; Development</option>
          <option>Not sure yet, help me choose</option>
        </select>
      </div>

      <div className="mt-5">
        <label htmlFor="message" className="mb-2 block text-sm font-semibold text-ink">
          Tell us about your project
        </label>
        <textarea
          id="message"
          name="message"
          rows={5}
          required
          placeholder="Goals, timeline, budget range, anything useful."
          aria-invalid={errors.message ? true : undefined}
          aria-describedby={errors.message ? "message-error" : undefined}
          className={`${inputClasses} resize-y`}
        />
        {errors.message && (
          <p id="message-error" className="mt-2 text-sm text-brand-300">
            {errors.message}
          </p>
        )}
      </div>

      <div className="mt-7">
        <SubmitButton />
        <p className="mt-4 text-center text-sm text-mist">
          By submitting, you agree to be contacted about your enquiry. We never
          share your details.
        </p>
      </div>
    </form>
  );
}
