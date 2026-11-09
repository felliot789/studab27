import type { Route } from "@/lib/schema";
import { OUTLOOK_LABELS, outlookCategory, publishedAwardRate } from "@/lib/scholarship-outlook";
import { External } from "./ui";

export default function ScholarshipOutlook({ route }: { route: Route }) {
  const category = outlookCategory(route), review = route.scholarshipOutlook;
  const rate = publishedAwardRate(route);
  return <details className="scholarship-outlook">
    <summary aria-label={`${OUTLOOK_LABELS[category]} outlook for ${route.scholarshipName}: why this label`}>
      <span className={`outlook-label outlook-${category.toLowerCase()}`}>{OUTLOOK_LABELS[category]}</span>
      <span className="outlook-disclosure">Why this label</span>
    </summary>
    <div className="outlook-evidence">
      <p>{review?.reason || "The reviewed catalogue does not yet establish how competitive this scholarship is. A priority label, a budget estimate, or automatic consideration cannot establish an individual chance of winning."}</p>
      {review && <p className="outlook-scope">{review.scope}</p>}
      {rate && review?.publishedRate ? <p><strong>Published award rate: {rate}</strong><br />{review.publishedRate.cycle} · {review.publishedRate.population}<br />{review.publishedRate.recipients.toLocaleString("en-GB")} recipients / {review.publishedRate.applicants.toLocaleString("en-GB")} applicants. Historical cohort result; not an individual award probability.</p> : <p className="outlook-scope">No matching scholarship award rate recorded.</p>}
      {review?.evidence.map(source => <div key={source.url}><External href={source.url}>{new URL(source.url).hostname}</External>{source.finding && <p>{source.finding}</p>}</div>)}
      {review ? <small>Planning assessment inferred from sources reviewed {review.reviewedAt}. Eligibility and funding adequacy still need separate checks.</small> : <External href={route.officialSourceUrl}>Open official scholarship information</External>}
    </div>
  </details>;
}
