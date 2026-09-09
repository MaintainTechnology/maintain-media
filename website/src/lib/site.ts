// TODO: replace with the real production domain before going live.
export const siteUrl = "https://maintainmedia.com.au";

export const siteName = "Maintain Media";

export const contactDetails = {
  email: "jon@maintainaudits.com.au",
  phone: "+61 414 530 836",
  phoneHref: "tel:+61414530836",
  location: "Brisbane, QLD, Australia",
  hours: "Mon to Fri, 8:30am to 5:30pm AEST",
};

export const navLinks = [
  { href: "/", label: "Home" },
  { href: "/services", label: "Services" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
] as const;

export const serviceLinks = [
  { href: "/services#brand", label: "Brand & Creative" },
  { href: "/services#performance", label: "Digital & Performance" },
  { href: "/services#content", label: "Content & Social" },
  { href: "/services#web", label: "Web & Development" },
] as const;
