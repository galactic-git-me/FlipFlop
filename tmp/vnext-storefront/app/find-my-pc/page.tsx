import type { Metadata } from "next";
import FindMyPcJourney from "./FindMyPcJourney";

export const metadata: Metadata = {
  title: "Find My PC",
  description: "Tell FlipFlop what you need. We will work out the sensible performance starting point.",
};

export default function FindMyPcPage() {
  return <FindMyPcJourney />;
}
