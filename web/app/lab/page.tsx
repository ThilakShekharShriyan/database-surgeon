import { redirect } from "next/navigation";

/** Lab / workbench folded into Live surgery for the submission surface. */
export default function LabRedirect() {
  redirect("/demo");
}
