import type { Metadata } from "next";
import { contactDetails } from "@/lib/site";

export const metadata: Metadata = {
  title: "Business research notice",
  description: "How Maintain Media handles business records and reviewed website evidence for its limited internal research pilot.",
};

export default function BusinessResearchNotice() {
  const linkStyle = "text-brand-300 underline underline-offset-4 hover:text-ink";
  return <article className="shell py-16 md:py-24">
    <div className="max-w-3xl">
      <p className="text-sm text-mist">Updated 11 September 2026</p>
      <h1 className="mt-4 font-display text-4xl font-bold tracking-tight md:text-5xl">Business research notice</h1>
      <p className="mt-6 text-lg leading-relaxed text-ink-2">Maintain Media is the trading name used for this limited business research pilot. This notice explains the information we collect, why we keep it and how to contact us about it.</p>

      <section className="mt-10 space-y-4 leading-relaxed text-ink-2" aria-labelledby="research-purpose">
        <h2 id="research-purpose" className="font-display text-2xl font-bold text-ink">What we collect and why</h2>
        <p>We use the public <a className={linkStyle} href="https://www.data.qld.gov.au/dataset/qbcc-licensed-contractors-register/resource/25608781-b28c-44f8-8545-0ab18d84082f" target="_blank" rel="noreferrer">QBCC Licensed Contractors Register</a> and a business’s own website after a staff reviewer checks its identity and site terms. The register is provided by the State of Queensland (Queensland Building and Construction Commission) under <a className={linkStyle} href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>. We reformat and filter it; our reviews are separate and do not imply QBCC endorsement.</p>
        <p>Research records may include a business or licensee name, ABN, licence details, business address, classification, public Australian phone numbers and the evidence for our checks. A business record can identify an individual, such as a sole trader.</p>
        <p>A separate early validation scope permits the public <a className={linkStyle} href="https://abr.business.gov.au/Tools/BulkExtract" target="_blank" rel="noreferrer">ABN Lookup bulk extract</a> from the Australian Business Register. This weekly XML publication includes ABN status and effective date, entity type, legal, business and trading names, state and postcode, and GST status and registration date. Names can identify individuals. We use these fields privately to validate the source, establish a starting reference list, compare later publications and review matching accuracy. Publication of this notice does not mean that an import or matching review has passed.</p>
        <p>The first accepted ABR list is a baseline: it creates no new-business events or leads. A later change is an observed registration change, not proof that a business has just formed. The bulk extract supplies no phone numbers or email addresses, and gives no permission to contact a business. This ABR scope does not authorise website collection or transfer of ABR records to Google Sheets or GoHighLevel.</p>
        <p>The <a className={linkStyle} href="https://data.gov.au/data/dataset/abn-bulk-extract" target="_blank" rel="noreferrer">ABN Lookup bulk data</a> is attributed to the Australian Business Register / ABN Lookup under <a className={linkStyle} href="https://creativecommons.org/licenses/by/3.0/au/" target="_blank" rel="noreferrer">CC BY 3.0 Australia</a>. We normalise and compare it. Our modifications and assessments do not imply endorsement by the publisher.</p>
        <p>We use these records for internal research and to assess whether a business fits Maintain Media’s services. This pilot does not authorise outreach. The system does not send messages, make calls or enrol businesses in campaigns. Transfers to Google Sheets remain disabled.</p>
        <p>Website collection is manually requested for a reviewed business and limited to phone details. Email addresses are not extracted into lead lists. An ordinary page capture may incidentally contain an email address or other information on that page. Finding a public phone number does not establish permission to call it.</p>
      </section>

      <section className="mt-10 space-y-4 leading-relaxed text-ink-2" aria-labelledby="research-handoff">
        <h2 id="research-handoff" className="font-display text-2xl font-bold text-ink">A separately reviewed GoHighLevel transfer</h2>
        <p>If an authorised reviewer separately approves an eligible record, we may copy a limited business summary and one reviewed phone number into Maintain Media’s GoHighLevel account for internal review. Do Not Disturb stays on. This does not authorise calls, messages or campaign enrolment. We do not transfer page captures, private evidence excerpts or email addresses in this scope.</p>
        <p>HighLevel’s <a className={linkStyle} href="https://www.gohighlevel.com/sub-processors" target="_blank" rel="noreferrer">published provider list</a> identifies core storage in the United States and service or support in the United States and India. The providers used by optional features and further support locations are not fully verified for our account.</p>
        <p>HighLevel’s <a className={linkStyle} href="https://www.gohighlevel.com/data-processing-agreement" target="_blank" rel="noreferrer">data processing agreement</a> excludes isolated backup copies from its deletion section. We have not verified a fixed expiry for those copies. Our retention and objection process clears unnecessary CRM fields created by the lead engine, but we do not claim immediate erasure from all provider backups.</p>
      </section>

      <section className="mt-10 space-y-4 leading-relaxed text-ink-2" aria-labelledby="research-storage">
        <h2 id="research-storage" className="font-display text-2xl font-bold text-ink">Access, storage and retention</h2>
        <p>Research records and page evidence are encrypted in our private AWS Sydney service. The staff website uses Vercel server functions in Sydney and Clerk for staff sign-in. Access is restricted to approved staff. Platform support and other processing countries have not all been verified; we do not claim that every part of processing takes place only in Australia.</p>
        <p>Ordinary website captures are kept for up to 90 days. Business profiles are kept for up to 180 days from the last qualifying event, or removed within 30 days after a restriction where applicable. A GoHighLevel transfer does not restart these periods. Encrypted queued website requests expire after 24 hours. Raw QBCC and ABR source files have a 30-day maximum; accepted analytical source snapshots have a 90-day maximum. Abandoned source staging is removed after seven days.</p>
        <p>The limited pilot does not create a seven-year selected-contact evidence archive. Minimal restriction records can remain to prevent a removed or restricted business from being added again.</p>
      </section>

      <section className="mt-10 space-y-4 leading-relaxed text-ink-2" aria-labelledby="research-requests">
        <h2 id="research-requests" className="font-display text-2xl font-bold text-ink">Ask about a record or raise a concern</h2>
        <p>Email <a className={linkStyle} href={`mailto:${contactDetails.email}`}>{contactDetails.email}</a>, Maintain Media’s current published contact, to request access or correction, ask where a record came from, request a restriction or raise a complaint. Include the business name and enough information for us to identify the record. We may need to confirm your connection to the business before disclosing private information.</p>
        <p>This page is a public explanation of the pilot. Publishing it does not mean that every person in a source record has been individually notified. It is not a claim of legal certification or a qualified adviser’s review.</p>
      </section>
    </div>
  </article>;
}
