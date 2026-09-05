import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MoodMix",
  description: "Detect your mood from voice or text, get a Spotify playlist.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
