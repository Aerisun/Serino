import { Label } from "./Label";
import { HelpIcon } from "./HelpIcon";
import type { ReactNode } from "react";

interface LabelWithHelpProps {
  children: ReactNode;
  tip?: ReactNode;
  htmlFor?: string;
}

export function LabelWithHelp({ children, tip, htmlFor }: LabelWithHelpProps) {
  return (
    <Label htmlFor={htmlFor} className="inline-flex items-center gap-1.5">
      {children}
      {tip && <HelpIcon tip={tip} />}
    </Label>
  );
}
