import { Link } from "react-router-dom";
import { ar } from "../i18n/ar";

export interface BreadcrumbItem {
  /** Visible label. */
  label: string;
  /** Target route. Omit for the current (trailing) page. */
  to?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <nav aria-label={ar.app.breadcrumbs.label} className="breadcrumbs">
      <ol>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`}>
              {item.to && !isLast ? (
                <Link to={item.to}>{item.label}</Link>
              ) : (
                <span aria-current={isLast ? "page" : undefined}>
                  {item.label}
                </span>
              )}
              {!isLast && (
                <span className="breadcrumb-separator" aria-hidden="true">
                  ‹
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
