import type { Metadata, Viewport } from "next";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://themoodmix.vercel.app";
const DESCRIPTION =
  "Say or type how you feel. MoodMix reads the mood and finds Spotify tracks to match it or lift it.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "MoodMix: Your Mood, Our Music",
  description: DESCRIPTION,
  applicationName: "MoodMix",
  appleWebApp: { capable: true, title: "MoodMix", statusBarStyle: "black-translucent" },
  formatDetection: { telephone: false },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "MoodMix",
    title: "MoodMix: Your Mood, Our Music",
    description: DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: "MoodMix: Your Mood, Our Music", description: DESCRIPTION },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Draw under the notch / home indicator; globals.css pads with safe-area insets.
  viewportFit: "cover",
  themeColor: "#14151d",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
