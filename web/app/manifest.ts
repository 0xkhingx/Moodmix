import type { MetadataRoute } from "next";

// Installable on phones ("Add to Home Screen" opens full screen, Cuzzon dark).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MoodMix: Your Mood, Our Music",
    short_name: "MoodMix",
    description: "Say or type how you feel. MoodMix reads the mood and finds Spotify tracks to match it or lift it.",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#14151d",
    theme_color: "#14151d",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
